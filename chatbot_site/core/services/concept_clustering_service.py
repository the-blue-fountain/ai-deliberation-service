"""Service for generating concept cluster visualizations from user conversations."""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Dict, List, Tuple

import networkx as nx
import plotly.graph_objects as go
from django.conf import settings

from ..models import DiscussionSession
from .openai_client import get_openai_client


logger = logging.getLogger(__name__)


class ConceptClusteringService:
    """Generate concept cluster visualizations from user conversations."""

    def __init__(self, session: DiscussionSession) -> None:
        self.session = session
        self.client = get_openai_client()

    def collect_all_concepts(self) -> Dict[int, List[str]]:
        """Collect all unique concepts from all users in the session.
        
        Returns:
            Dictionary mapping user_id to list of their concepts
        """
        user_concepts = {}
        for conversation in self.session.conversations.filter(unique_concepts__isnull=False):
            if conversation.unique_concepts:
                user_concepts[conversation.user_id] = conversation.unique_concepts
        return user_concepts

    def generate_concept_relationships(self, user_concepts: Dict[int, List[str]]) -> List[Tuple[str, str, float]]:
        """Use LLM to identify semantic relationships between concepts.
        
        Args:
            user_concepts: Dictionary mapping user_id to list of concepts
        
        Returns:
            List of tuples (concept1, concept2, similarity_score) representing edges
        """
        # Flatten all concepts
        all_concepts = []
        for concepts in user_concepts.values():
            all_concepts.extend(concepts)
        
        # Get unique concepts with counts
        concept_counts = Counter(all_concepts)
        unique_concepts = list(concept_counts.keys())
        
        if len(unique_concepts) < 2:
            return []
        
        # Use LLM to identify relationships
        system_prompt = (
            "You are analyzing concepts from a discussion to identify semantic relationships. "
            "Given a list of concepts, identify which concepts are related to each other and "
            "rate the strength of their relationship from 0.0 (unrelated) to 1.0 (very strongly related). "
            "Only include relationships with similarity >= 0.3. Return JSON with a 'relationships' array "
            "where each item has: 'concept1', 'concept2', 'similarity' (float 0-1)."
        )
        
        user_prompt = (
            "Here are concepts discussed by participants:\n\n"
            + "\n".join(f"- {concept} (mentioned {count} time{'s' if count > 1 else ''})" 
                       for concept, count in concept_counts.most_common())
            + "\n\nIdentify semantic relationships between these concepts."
        )
        
        try:
            completion = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            
            content = completion.choices[0].message.content or "{}"
            parsed = json.loads(content)
            relationships = parsed.get("relationships", [])
            
            # Convert to tuple format
            edges = []
            for rel in relationships:
                c1 = rel.get("concept1", "")
                c2 = rel.get("concept2", "")
                sim = float(rel.get("similarity", 0.0))
                if c1 and c2 and sim >= 0.3:
                    edges.append((c1, c2, sim))
            
            return edges
            
        except Exception as exc:
            logger.exception("Failed to generate concept relationships: %s", exc)
            # Fallback: create simple co-occurrence based connections
            return self._generate_fallback_relationships(user_concepts)

    def _generate_fallback_relationships(self, user_concepts: Dict[int, List[str]]) -> List[Tuple[str, str, float]]:
        """Generate relationships based on co-occurrence (users discussing same concepts).
        
        Args:
            user_concepts: Dictionary mapping user_id to list of concepts
        
        Returns:
            List of tuples (concept1, concept2, co-occurrence_score)
        """
        # Flatten and get unique concepts
        all_concepts_list = []
        for concepts in user_concepts.values():
            all_concepts_list.extend(concepts)
        unique_concepts = list(set(all_concepts_list))
        
        if len(unique_concepts) < 2:
            return []
        
        # Build co-occurrence matrix
        edges = []
        for i, c1 in enumerate(unique_concepts):
            for c2 in unique_concepts[i+1:]:
                # Count how many users discussed both concepts
                co_users = sum(1 for concepts in user_concepts.values() 
                             if c1 in concepts and c2 in concepts)
                if co_users > 0:
                    # Score based on co-occurrence frequency
                    score = min(1.0, co_users / len(user_concepts) * 1.5)
                    edges.append((c1, c2, score))
        
        return edges

    def generate_network_visualization(self) -> str:
        """Generate an interactive network visualization of concept clusters.
        
        Returns:
            HTML string containing the Plotly visualization
        """
        user_concepts = self.collect_all_concepts()
        
        if not user_concepts:
            return "<p class='text-muted'>No concept data available yet. Users must complete their conversations first.</p>"
        
        # Get concept frequency
        all_concepts_flat = []
        for concepts in user_concepts.values():
            all_concepts_flat.extend(concepts)
        concept_counts = Counter(all_concepts_flat)
        
        # Generate relationships
        edges = self.generate_concept_relationships(user_concepts)
        
        if not edges and len(concept_counts) == 1:
            # Single concept case
            concept = list(concept_counts.keys())[0]
            count = concept_counts[concept]
            return f"""
            <div class="alert alert-info">
                <h5>Single Concept Identified</h5>
                <p><strong>{concept}</strong> (mentioned {count} time{'s' if count > 1 else ''})</p>
            </div>
            """
        
        # Build network graph
        G = nx.Graph()
        
        # Add nodes with sizes based on frequency
        for concept, count in concept_counts.items():
            G.add_node(concept, weight=count)
        
        # Add edges
        for c1, c2, weight in edges:
            if c1 in G.nodes and c2 in G.nodes:
                G.add_edge(c1, c2, weight=weight)
        
        # If no edges, create a minimal connected graph
        if G.number_of_edges() == 0 and G.number_of_nodes() > 1:
            nodes = list(G.nodes())
            # Connect in a circle to make it viewable
            for i in range(len(nodes)):
                G.add_edge(nodes[i], nodes[(i+1) % len(nodes)], weight=0.3)
        
        # Layout
        try:
            pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
        except Exception:
            # Fallback to circular layout
            pos = nx.circular_layout(G)
        
        # Extract edge traces
        edge_traces = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            weight = G[edge[0]][edge[1]].get('weight', 0.5)
            
            edge_trace = go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(width=weight*3, color='rgba(125,125,125,0.5)'),
                hoverinfo='none',
                showlegend=False,
            )
            edge_traces.append(edge_trace)
        
        # Extract node traces
        node_x = []
        node_y = []
        node_text = []
        node_sizes = []
        node_colors = []
        
        max_count = max(concept_counts.values())
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            count = concept_counts[node]
            node_text.append(f"{node}<br>Mentioned: {count} times")
            # Size proportional to frequency (10-40 range)
            node_sizes.append(10 + (count / max_count) * 30)
            # Color based on degree (connectivity)
            degree = G.degree[node]
            node_colors.append(degree)
        
        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode='markers+text',
            text=[node for node in G.nodes()],
            textposition="top center",
            textfont=dict(size=10, color='black'),
            hoverinfo='text',
            hovertext=node_text,
            marker=dict(
                size=node_sizes,
                color=node_colors,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(
                    title="Connections",
                    thickness=15,
                    x=1.02,
                ),
                line=dict(width=2, color='white'),
            ),
            showlegend=False,
        )
        
        # Create figure
        fig = go.Figure(data=edge_traces + [node_trace])
        
        fig.update_layout(
            title=dict(
                text=f"Concept Network - {self.session.topic}<br><sub>Node size = frequency, Color = connectivity</sub>",
                x=0.5,
                xanchor='center',
            ),
            showlegend=False,
            hovermode='closest',
            margin=dict(b=20, l=5, r=5, t=60),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor='rgba(245,245,245,0.9)',
            height=600,
        )
        
        # Convert to HTML
        html = fig.to_html(include_plotlyjs='cdn', div_id='concept-network-viz')
        return html

    def generate_concept_summary_markdown(self) -> str:
        """Generate a markdown summary of concept clusters.
        
        Returns:
            Markdown formatted string summarizing concepts and relationships
        """
        user_concepts = self.collect_all_concepts()
        
        if not user_concepts:
            return "_No concept data available yet._"
        
        # Get all concepts with frequency
        all_concepts_flat = []
        for concepts in user_concepts.values():
            all_concepts_flat.extend(concepts)
        concept_counts = Counter(all_concepts_flat)
        
        # Build markdown
        md = f"## Concept Analysis\n\n"
        md += f"**Total Participants:** {len(user_concepts)}  \n"
        md += f"**Unique Concepts:** {len(concept_counts)}  \n"
        md += f"**Total Mentions:** {sum(concept_counts.values())}  \n\n"
        
        md += "### Most Frequently Discussed Concepts\n\n"
        for concept, count in concept_counts.most_common(10):
            percentage = (count / len(user_concepts)) * 100
            md += f"- **{concept}** - {count} mentions ({percentage:.0f}% of participants)\n"
        
        # Identify concepts by user
        md += "\n### Concept Distribution by Participant\n\n"
        for user_id in sorted(user_concepts.keys()):
            concepts = user_concepts[user_id]
            md += f"**User {user_id}:** {', '.join(concepts)}\n\n"
        
        return md
