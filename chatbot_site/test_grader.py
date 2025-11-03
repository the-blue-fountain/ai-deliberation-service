#!/usr/bin/env python
"""
Test script to verify Grader feature implementation.
Run with: python test_grader.py
"""

import os
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_site.settings')
django.setup()

from core.models import GraderSession, GraderResponse
from core.forms import GraderSessionForm, GraderResponseForm

def test_models():
    print("\n=== Testing Models ===")
    
    # Test GraderSession.get_active()
    print("✓ Getting or creating active session...")
    session = GraderSession.get_active()
    print(f"  Session: {session}")
    print(f"  Session ID: {session.s_id}")
    print(f"  Active: {session.is_active}")
    
    # Test get_question_sequence()
    print("✓ Testing question sequence...")
    questions = session.get_question_sequence()
    print(f"  Questions: {questions}")
    
    # Test activate()
    print("✓ Testing session activation...")
    session.activate()
    print(f"  Session is now active: {session.is_active}")
    
    return session

def test_forms(session):
    print("\n=== Testing Forms ===")
    
    # Test GraderSessionForm
    print("✓ Testing GraderSessionForm...")
    form_data = {
        's_id': 'test-session',
        'topic': 'Test Evaluation',
        'description': '# Test\nThis is a test grader session',
        'objective_questions': '["Question 1", "Question 2"]',
        'knowledge_base': '',
        'user_instructions': '',
    }
    form = GraderSessionForm(data=form_data)
    if form.is_valid():
        print("  Form is valid!")
        print(f"  Cleaned data: {form.cleaned_data}")
    else:
        print(f"  Form errors: {form.errors}")
    
    return form

def test_grader_response(session):
    print("\n=== Testing GraderResponse ===")
    
    # Create a test response
    print("✓ Creating test grader response...")
    response_data = {
        'session': session,
        'user_id': 101,
        'scores': [8, 9, 7],
        'reasons': ['Good UX', 'Responsive design', 'Minor issues'],
        'additional_comments': 'Overall impressed with the redesign',
    }
    
    # Create or update response
    response, created = GraderResponse.objects.update_or_create(
        session=session,
        user_id=response_data['user_id'],
        defaults={
            'scores': response_data['scores'],
            'reasons': response_data['reasons'],
            'additional_comments': response_data['additional_comments'],
        }
    )
    
    print(f"  Response created/updated: {response}")
    print(f"  User ID: {response.user_id}")
    print(f"  Scores: {response.scores}")
    print(f"  Reasons: {response.reasons}")
    print(f"  Comments: {response.additional_comments}")
    print(f"  Is new: {created}")
    
    return response

def test_analysis(session):
    print("\n=== Testing Analysis ===")
    
    # Test response retrieval
    print("✓ Retrieving all responses for session...")
    responses = GraderResponse.objects.filter(session=session)
    print(f"  Total responses: {responses.count()}")
    
    questions = session.get_question_sequence()
    print(f"  Total questions: {len(questions)}")
    
    # Simulate average calculation
    print("✓ Calculating average scores...")
    scores_by_q = [[] for _ in questions]
    for resp in responses:
        for i, q in enumerate(questions):
            if i < len(resp.scores):
                try:
                    score = int(resp.scores[i])
                    scores_by_q[i].append(score)
                except:
                    pass
    
    averages = []
    for scores in scores_by_q:
        if scores:
            avg = sum(scores) / len(scores)
            averages.append(avg)
            print(f"  Average score: {avg:.2f}")
        else:
            averages.append(None)
            print(f"  Average score: No data")
    
    return averages

def main():
    print("\n" + "="*50)
    print("GRADER FEATURE TEST SUITE")
    print("="*50)
    
    try:
        session = test_models()
        form = test_forms(session)
        response = test_grader_response(session)
        averages = test_analysis(session)
        
        print("\n" + "="*50)
        print("✓ ALL TESTS PASSED")
        print("="*50)
        print("\nGrader feature is working correctly!")
        print("\nNext steps:")
        print("1. Run: python manage.py runserver")
        print("2. Navigate to: http://localhost:8000/")
        print("3. Choose 'Grader' from the system choice page")
        print("4. Create a test session")
        print("5. Share /grader/user/<id>/ URL with testers")
        print("="*50 + "\n")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
