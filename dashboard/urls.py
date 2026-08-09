from django.urls import path

from . import careers_views, views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    # Auth
    path("login/", views.DashboardLoginView.as_view(), name="login"),
    path("logout/", views.DashboardLogoutView.as_view(), name="logout"),
    path(
        "password-reset/",
        views.DashboardPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/sent/",
        views.DashboardPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        views.DashboardPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/done/",
        views.DashboardPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    # Own account
    path("account/", views.account, name="account"),
    path(
        "account/password/",
        views.DashboardPasswordChangeView.as_view(),
        name="password_change",
    ),
    # Users
    path("users/", views.user_list, name="user_list"),
    path("users/add/", views.user_create, name="user_create"),
    path("users/<int:pk>/edit/", views.user_update, name="user_update"),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),
    # Roles (auth groups)
    path("roles/", views.group_list, name="group_list"),
    path("roles/add/", views.group_create, name="group_create"),
    path("roles/<int:pk>/edit/", views.group_update, name="group_update"),
    path("roles/<int:pk>/delete/", views.group_delete, name="group_delete"),
    # Services
    path("services/", views.service_list, name="service_list"),
    path("services/add/", views.service_create, name="service_create"),
    path("services/<int:pk>/edit/", views.service_update, name="service_update"),
    path("services/<int:pk>/delete/", views.service_delete, name="service_delete"),
    # Vacancies
    path("vacancies/", careers_views.vacancy_list, name="vacancy_list"),
    path("vacancies/add/", careers_views.vacancy_create, name="vacancy_create"),
    path("vacancies/<int:pk>/edit/", careers_views.vacancy_update, name="vacancy_update"),
    path("vacancies/<int:pk>/delete/", careers_views.vacancy_delete, name="vacancy_delete"),
    # Applications
    path("applications/", careers_views.application_list, name="application_list"),
    path("applications/<int:pk>/", careers_views.application_detail, name="application_detail"),
    path(
        "applications/<int:pk>/resume/",
        careers_views.application_resume,
        name="application_resume",
    ),
    # Site settings
    path("settings/", careers_views.site_settings, name="site_settings"),
    # Team
    path("team/", careers_views.team_list, name="team_list"),
    path("team/add/", careers_views.team_create, name="team_create"),
    path("team/<int:pk>/edit/", careers_views.team_update, name="team_update"),
    path("team/<int:pk>/delete/", careers_views.team_delete, name="team_delete"),
    # Consultations
    path("consultations/", careers_views.consultation_list, name="consultation_list"),
    path(
        "consultations/<int:pk>/",
        careers_views.consultation_detail,
        name="consultation_detail",
    ),
    # Enquiries
    path("enquiries/", views.enquiry_list, name="enquiry_list"),
    path("enquiries/<int:pk>/", views.enquiry_detail, name="enquiry_detail"),
]
