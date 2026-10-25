from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from market.forms import ProfileForm
from market.models import Listing, Message, Thread


class AccessControlTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="password")
        self.buyer = User.objects.create_user(username="buyer", password="password")
        self.unrelated = User.objects.create_user(username="unrelated", password="password")
        self.listing = Listing.objects.create(
            owner=self.owner,
            title="Textbook",
            description="Used textbook",
            price="20.00",
            category="books",
        )
        self.thread = Thread.objects.create(listing=self.listing, buyer=self.buyer)

    def test_user_cannot_edit_another_users_listing(self):
        self.client.force_login(self.unrelated)

        response = self.client.post(
            reverse("listing_edit", args=[self.listing.pk]),
            {
                "title": "Changed",
                "description": self.listing.description,
                "price": self.listing.price,
                "category": self.listing.category,
                "seller_note": "",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, "Textbook")

    def test_user_cannot_mark_another_users_listing_sold(self):
        self.client.force_login(self.unrelated)

        response = self.client.post(reverse("listing_sold", args=[self.listing.pk]))

        self.assertEqual(response.status_code, 404)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "available")

    def test_user_cannot_delete_another_users_listing(self):
        self.client.force_login(self.unrelated)

        response = self.client.post(reverse("listing_delete", args=[self.listing.pk]))

        self.assertEqual(response.status_code, 404)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "available")

    def test_unrelated_user_cannot_access_or_post_to_thread(self):
        self.client.force_login(self.unrelated)
        url = reverse("thread_detail", args=[self.thread.pk])

        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"body": "intrusion"}).status_code, 403)
        self.assertFalse(Message.objects.filter(thread=self.thread).exists())

    def test_buyer_can_access_and_post_to_thread(self):
        self.client.force_login(self.buyer)
        url = reverse("thread_detail", args=[self.thread.pk])

        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"body": "Is this available?"})

        self.assertRedirects(response, url)
        self.assertTrue(Message.objects.filter(thread=self.thread, sender=self.buyer).exists())

    def test_listing_owner_can_access_and_post_to_thread(self):
        self.client.force_login(self.owner)
        url = reverse("thread_detail", args=[self.thread.pk])

        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"body": "Yes, it is."})

        self.assertRedirects(response, url)
        self.assertTrue(Message.objects.filter(thread=self.thread, sender=self.owner).exists())

    def test_profile_form_does_not_expose_or_update_is_staff(self):
        self.assertNotIn("is_staff", ProfileForm().fields)
        self.client.force_login(self.unrelated)

        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "New",
                "last_name": "Name",
                "email": "new@example.com",
                "is_staff": "on",
            },
        )

        self.assertRedirects(response, reverse("profile"))
        self.unrelated.refresh_from_db()
        self.assertEqual(self.unrelated.first_name, "New")
        self.assertEqual(self.unrelated.last_name, "Name")
        self.assertEqual(self.unrelated.email, "new@example.com")
        self.assertFalse(self.unrelated.is_staff)

    def test_owner_can_edit_mark_sold_and_delete_own_listing(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("listing_edit", args=[self.listing.pk]),
            {
                "title": "Updated textbook",
                "description": self.listing.description,
                "price": self.listing.price,
                "category": self.listing.category,
                "seller_note": "Meet on campus",
            },
        )
        self.assertRedirects(response, reverse("listing_detail", args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, "Updated textbook")

        response = self.client.post(reverse("listing_sold", args=[self.listing.pk]))
        self.assertRedirects(response, reverse("listing_detail", args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "sold")

        response = self.client.post(reverse("listing_delete", args=[self.listing.pk]))
        self.assertRedirects(response, reverse("home"))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "removed")
