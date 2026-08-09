from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("about/team/<slug:slug>/", views.team_member, name="team_member"),
    path("services/", views.services, name="services"),
    path("services/<slug:slug>/", views.service_detail, name="service_detail"),
    path("ndis-support/", views.ndis_support, name="ndis_support"),
    path("careers/", views.careers, name="careers"),
    path("careers/apply/", views.speculative_application, name="apply"),
    path("careers/<slug:slug>/", views.vacancy_detail, name="vacancy_detail"),
    path("contact/", views.contact, name="contact"),
    path("book-a-consultation/", views.consultation, name="consultation"),
    path("book-a-consultation/thank-you/", views.consultation_booked, name="consultation_booked"),
    path("faq/", views.faq, name="faq"),
    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),
    path("terms/", views.terms, name="terms"),
]
