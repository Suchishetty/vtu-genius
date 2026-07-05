from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

# Create your views here.

@login_required
def dashboard_home(request):
    profile = request.user.student_profile
    return HttpResponse(
        f"Welcome, {profile.full_name}. Branch: {profile.branch}. Semester: {profile.semester}."
    )
