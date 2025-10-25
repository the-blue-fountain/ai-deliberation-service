from django.db import models
from django.contrib.postgres.fields import JSONField


class DiscussionSession(models.Model):
	"""
	Stores one full discussion session.

	Fields:
	- s_id: string id provided by moderator (unique)
	- moderator_id: integer id for moderator (default 0)
	- num_users: number of participant users
	- user_1 .. user_10: JSON objects storing conversation data for each user
	- info: JSON/text storing the moderator-provided information used for RAG
	- results: JSON storing final summary / analysis returned by LLM
	- created_at, updated_at timestamps
	"""

	s_id = models.CharField(max_length=100, unique=True)
	moderator_id = models.IntegerField(default=0)
	num_users = models.IntegerField(default=0)

	user_1 = JSONField(blank=True, null=True)
	user_2 = JSONField(blank=True, null=True)
	user_3 = JSONField(blank=True, null=True)
	user_4 = JSONField(blank=True, null=True)
	user_5 = JSONField(blank=True, null=True)
	user_6 = JSONField(blank=True, null=True)
	user_7 = JSONField(blank=True, null=True)
	user_8 = JSONField(blank=True, null=True)
	user_9 = JSONField(blank=True, null=True)
	user_10 = JSONField(blank=True, null=True)

	info = JSONField(blank=True, null=True)
	results = JSONField(blank=True, null=True)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"DiscussionSession(s_id={self.s_id}, users={self.num_users})"
