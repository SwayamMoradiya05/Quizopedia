"""
URL configuration for quizopedia project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from report_cards.views import (
    RoleBasedLoginView,
    admin_dashboard,
    home,
    profile,
    question_create,
    question_delete,
    question_list,
    question_update,
    resend_student_otp,
    review_student_profile_change,
    subject_create,
    subject_delete,
    subject_list,
    subject_update,
    student_dashboard,
    student_otp_verify,
    student_profile_edit,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('accounts/login/', RoleBasedLoginView.as_view(), name='login'),
    path('accounts/otp/', student_otp_verify, name='student_otp_verify'),
    path('accounts/otp/resend/', resend_student_otp, name='resend_student_otp'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('dashboard/admin/', admin_dashboard, name='admin_dashboard'),
    path('dashboard/admin/questions/', question_list, name='question_list'),
    path('dashboard/admin/questions/new/', question_create, name='question_create'),
    path(
        'dashboard/admin/questions/<int:question_id>/edit/',
        question_update,
        name='question_update',
    ),
    path(
        'dashboard/admin/questions/<int:question_id>/delete/',
        question_delete,
        name='question_delete',
    ),
    path('dashboard/admin/subjects/', subject_list, name='subject_list'),
    path('dashboard/admin/subjects/new/', subject_create, name='subject_create'),
    path(
        'dashboard/admin/subjects/<int:subject_id>/edit/',
        subject_update,
        name='subject_update',
    ),
    path(
        'dashboard/admin/subjects/<int:subject_id>/delete/',
        subject_delete,
        name='subject_delete',
    ),
    path('dashboard/student/', student_dashboard, name='student_dashboard'),
    path('profile/', profile, name='profile'),
    path('profile/student/edit/', student_profile_edit, name='student_profile_edit'),
    path(
        'profile/changes/<int:change_id>/<str:decision>/',
        review_student_profile_change,
        name='review_student_profile_change',
    ),
]
