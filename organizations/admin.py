from django.contrib import admin
from .models import Organization, Membership, ServiceMembership


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display  = ('name', 'sector', 'plan', 'country', 'is_active', 'created_at')
    list_filter   = ('sector', 'plan', 'is_active')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display  = ('user', 'organization', 'role', 'joined_at')
    list_filter   = ('role',)
    search_fields = ('user__username', 'organization__name')
@admin.register(ServiceMembership)
class ServiceMembershipAdmin(admin.ModelAdmin):
    list_display  = ('user', 'organization', 'service', 'role', 'assigned_at')
    list_filter   = ('role', 'organization', 'service')
    search_fields = ('user__username', 'service')