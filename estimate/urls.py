from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('create-estimate/', views.create_estimate, name='create_estimate'),
    path('manage-paver-blocks/', views.manage_paver_blocks, name='manage_paver_blocks'),
    path('delete-paver-block/<int:paver_block_id>/', views.delete_paver_block, name='delete_paver_block'),
    path('generate-pdf/<int:estimate_id>/', views.generate_pdf, name='generate_pdf'),
    path('delete-estimate/<int:estimate_id>/', views.delete_estimate, name='delete_estimate'),
] 