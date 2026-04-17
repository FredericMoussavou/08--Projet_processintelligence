from django.contrib import admin
from .models import Procedure, Step, StepDependency, Rule, AuditReport, ChangeRequest

class StepInline(admin.TabularInline):
    model = Step
    extra = 0
    fields = ('step_order', 'title', 'actor_role', 'action_verb', 'automation_score', 'compliance_status')
    readonly_fields = ('automation_score',)
@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):
    list_display  = ('title', 'organization', 'service', 'version', 'status', 'owner', 'created_at')
    list_filter   = ('status', 'organization')
    search_fields = ('title', 'description')
    inlines       = [StepInline]


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