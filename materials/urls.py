from django.urls import path

from . import views

app_name = "materials"

urlpatterns = [
    # Add new material (both Admin and Staff)
    path("new/", views.MaterialCreateView.as_view(), name="create"),
    # Soft-deletes (admin only, POST + confirm; rows stay in DB)
    path("<int:pk>/delete/", views.MaterialDeleteView.as_view(),
         name="delete"),
    path("category/<int:pk>/delete/", views.CategoryDeleteView.as_view(),
         name="category_delete"),
    path("subcategory/<int:pk>/delete/",
         views.SubCategoryDeleteView.as_view(), name="subcategory_delete"),
]
