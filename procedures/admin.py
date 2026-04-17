from django.contrib import admin
from .models import Procedure, Step, StepDependency, Rule, AuditReport, ChangeRequest
from django.utils.html import format_html
from django.urls import reverse

class StepInline(admin.TabularInline):
    model = Step
    extra = 0
    fields = ('step_order', 'title', 'actor_role', 'action_verb', 'automation_score', 'compliance_status')
    readonly_fields = ('automation_score',)
@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):
    list_display  = ('title', 'organization', 'service', 'version', 'status', 'owner', 'created_at', 'audit_link')
    list_filter   = ('status', 'organization')
    search_fields = ('title', 'description')
    inlines       = [StepInline]

    def audit_link(self, obj):
        reports = obj.audit_reports.all()
        if reports.exists():
            latest = reports.latest('generated_at')
            url = reverse('admin:procedures_auditreport_change', args=[latest.id])
            return format_html('<a href="{}">📊 Voir rapport</a>', url)
        url = f"/api/procedures/{obj.id}/analyze/"
        return format_html('<a href="{}" onclick="fetch(this.href, {{method:\'POST\'}}).then(()=>location.reload()); return false;">⚡ Générer</a>', url)

    audit_link.short_description = 'Rapport d\'audit'

@admin.register(Step)
class StepAdmin(admin.ModelAdmin):
    list_display  = ('step_order', 'title', 'actor_role', 'action_verb', 'trigger_type', 'output_type', 'compliance_status', 'automation_score')
    list_filter   = ('trigger_type', 'output_type', 'compliance_status', 'is_recurring')
    search_fields = ('title', 'actor_role', 'action_verb')


@admin.register(StepDependency)
class StepDependencyAdmin(admin.ModelAdmin):
    list_display  = ('from_step', 'to_step', 'condition_label')


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display  = ('label', 'organization', 'severity', 'legal_ref', 'is_active')
    list_filter   = ('severity', 'is_active')
    search_fields = ('label', 'legal_ref')

@admin.register(AuditReport)
class AuditReportAdmin(admin.ModelAdmin):
    list_display  = ('procedure', 'score_optim', 'score_auto', 'generated_by', 'generated_at')
    list_filter   = ('generated_at',)


@admin.register(ChangeRequest)
class ChangeRequestAdmin(admin.ModelAdmin):
    list_display  = ('procedure', 'requested_by', 'reviewer', 'status', 'created_at', 'reviewed_at')
    list_filter   = ('status',)