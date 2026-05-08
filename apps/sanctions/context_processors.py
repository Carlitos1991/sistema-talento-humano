from .models import SanctionNotification

def pending_assignments(request):
    count = 0
    if request.user.is_authenticated and request.user.has_perm('sanctions.view_sanctionnotification'):
        queryset = SanctionNotification.objects.filter(status='EN_PROCESO')
        
        if not request.user.is_staff:
            queryset = queryset.filter(
                assignment_history__assigned_to=request.user,
                assignment_history__is_current=True
            )
            
        count = queryset.distinct().count()
        
    return {'sanctions_pending_assignments_count': count}