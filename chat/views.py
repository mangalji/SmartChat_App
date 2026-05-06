import json
import logging

logger = logging.getLogger(__name__)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Q
from django.utils import timezone
from django.conf import settings

from chat.models import Message, ChatGroup, GroupMember, GroupMessage

User = get_user_model()

# Allowed upload types & 10 MB max
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
ALLOWED_FILE_TYPES  = {'application/pdf', 'application/msword',
                       'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                       'application/zip', 'text/plain'}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024   # 10 MB

# Allowed file extensions (server-side validation)
ALLOWED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
ALLOWED_FILE_EXTS  = {'.pdf', '.doc', '.docx', '.zip', '.txt'}


# ──────────────────────────────────────────────
# CHAT HOME
# ──────────────────────────────────────────────
@login_required
def index(request):
    me            = request.user
    my_groups     = ChatGroup.objects.filter(members__user=me).prefetch_related('members')
    conversations = _build_conversations(me)
    return render(request, 'chat/index.html', {
        'conversations': conversations,
        'my_groups':     my_groups,
    })


# ──────────────────────────────────────────────
# 1-ON-1 DM ROOM
# ──────────────────────────────────────────────
@login_required
def dm_room(request, user_id):
    me    = request.user
    other = get_object_or_404(User, pk=user_id, is_active=True)

    if other == me:
        messages.error(request, "You can't chat with yourself.")
        return redirect('chat:index')

    history = Message.objects.filter(
        Q(sender=me, receiver=other) | Q(sender=other, receiver=me)
    ).order_by('timestamp').select_related('sender', 'receiver')

    # Mark as read
    history.filter(receiver=me, is_read=False).update(is_read=True)

    my_groups     = ChatGroup.objects.filter(members__user=me)
    conversations = _build_conversations(me)

    return render(request, 'chat/room.html', {
        'other':         other,
        'history':       history,
        'conversations': conversations,
        'my_groups':     my_groups,
        'room_type':     'dm',
        'unread_counts': _unread_counts(me),
    })


# ──────────────────────────────────────────────
# GROUP LIST
# ──────────────────────────────────────────────
@login_required
def group_list(request):
    me            = request.user
    my_groups     = ChatGroup.objects.filter(members__user=me).prefetch_related('members')
    conversations = _build_conversations(me)
    return render(request, 'chat/group_list.html', {
        'my_groups':     my_groups,
        'conversations': conversations,
    })


# ──────────────────────────────────────────────
# CREATE GROUP
# ──────────────────────────────────────────────
@login_required
def create_group(request):
    me        = request.user

    if request.method == 'POST':
        name        = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        member_ids  = request.POST.getlist('members')

        if not name:
            messages.error(request, 'Group name is required.')
            return render(request, 'chat/create_group.html')

        group = ChatGroup.objects.create(
            name=name, description=description, created_by=me
        )
        GroupMember.objects.create(group=group, user=me, role='admin')

        for uid in member_ids:
            try:
                u = User.objects.get(pk=uid)
                GroupMember.objects.get_or_create(
                    group=group, user=u, defaults={'role': 'member'}
                )
            except User.DoesNotExist:
                pass

        messages.success(request, f'Group "{name}" created!')
        return redirect('chat:group_room', group_id=group.pk)

    return render(request, 'chat/create_group.html')


# ──────────────────────────────────────────────
# GROUP ROOM
# ──────────────────────────────────────────────
@login_required
def group_room(request, group_id):
    me    = request.user
    group = get_object_or_404(ChatGroup, pk=group_id)

    membership = GroupMember.objects.filter(group=group, user=me).first()
    if not membership:
        messages.error(request, 'You are not a member of this group.')
        return redirect('chat:group_list')

    history   = GroupMessage.objects.filter(group=group).order_by('timestamp').select_related('sender')
    members   = GroupMember.objects.filter(group=group).select_related('user')
    my_groups = ChatGroup.objects.filter(members__user=me)
    conversations = _build_conversations(me)

    return render(request, 'chat/group_room.html', {
        'group':        group,
        'history':      history,
        'members':      members,
        'membership':   membership,
        'conversations': conversations,
        'my_groups':    my_groups,
        'room_type':    'group',
    })


# ──────────────────────────────────────────────
# ADD MEMBER
# ──────────────────────────────────────────────
@login_required
@require_POST
def add_member(request, group_id):
    me    = request.user
    group = get_object_or_404(ChatGroup, pk=group_id)

    if not GroupMember.objects.filter(group=group, user=me, role='admin').exists():
        messages.error(request, 'Only admins can add members.')
        return redirect('chat:group_room', group_id=group_id)

    uid = request.POST.get('user_id')
    try:
        u = User.objects.get(pk=uid)
        _, created = GroupMember.objects.get_or_create(
            group=group, user=u, defaults={'role': 'member'}
        )
        msg = f'{u.full_name} added.' if created else f'{u.full_name} is already a member.'
        messages.success(request, msg) if created else messages.info(request, msg)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')

    return redirect('chat:group_room', group_id=group_id)


# ──────────────────────────────────────────────
# REMOVE MEMBER
# ──────────────────────────────────────────────
@login_required
@require_POST
def remove_member(request, group_id):
    me    = request.user
    group = get_object_or_404(ChatGroup, pk=group_id)

    if not GroupMember.objects.filter(group=group, user=me, role='admin').exists():
        messages.error(request, 'Only admins can remove members.')
        return redirect('chat:group_room', group_id=group_id)

    uid = request.POST.get('user_id')
    try:
        u = User.objects.get(pk=uid)
        if u == me:
            messages.error(request, 'You cannot remove yourself. Use Leave Group.')
        else:
            GroupMember.objects.filter(group=group, user=u).delete()
            messages.success(request, f'{u.full_name} removed.')
    except User.DoesNotExist:
        messages.error(request, 'User not found.')

    return redirect('chat:group_room', group_id=group_id)


# ──────────────────────────────────────────────
# LEAVE GROUP
# ──────────────────────────────────────────────
@login_required
@require_POST
def leave_group(request, group_id):
    me    = request.user
    group = get_object_or_404(ChatGroup, pk=group_id)

    membership = GroupMember.objects.filter(group=group, user=me).first()
    if not membership:
        return redirect('chat:group_list')

    # If only admin — transfer or block
    if membership.role == 'admin':
        other_admins = GroupMember.objects.filter(
            group=group, role='admin'
        ).exclude(user=me)
        if not other_admins.exists():
            # Promote oldest member
            next_member = GroupMember.objects.filter(
                group=group
            ).exclude(user=me).order_by('joined').first()
            if next_member:
                next_member.role = 'admin'
                next_member.save(update_fields=['role'])
            else:
                # Last person — delete group
                group.delete()
                messages.success(request, 'Group deleted as you were the last member.')
                return redirect('chat:group_list')

    membership.delete()
    messages.success(request, f'You left "{group.name}".')
    return redirect('chat:group_list')


# ──────────────────────────────────────────────
# UPLOAD MEDIA  (Phase 5 — full validation)
# ──────────────────────────────────────────────
@login_required
@require_POST
def upload_media(request):
    me   = request.user
    file = request.FILES.get('file')

    if not file:
        return JsonResponse({'error': 'No file provided.'}, status=400)

    # Size check
    if file.size > MAX_UPLOAD_BYTES:
        return JsonResponse({'error': 'File too large. Max 10 MB.'}, status=400)

    content_type = file.content_type or ''

    # Extension check (prevents content-type spoofing)
    import os
    _, ext = os.path.splitext(file.name.lower())

    # Type check — verify BOTH content-type AND extension match
    if content_type in ALLOWED_IMAGE_TYPES and ext in ALLOWED_IMAGE_EXTS:
        media_type = 'image'
        # Validate image with Pillow (prevents disguised files)
        try:
            from PIL import Image
            img = Image.open(file)
            img.verify()     # Checks image integrity
            file.seek(0)     # Reset for Django to save
        except Exception:
            return JsonResponse(
                {'error': 'Invalid image file. The file appears to be corrupted.'},
                status=400
            )
    elif content_type in ALLOWED_FILE_TYPES and ext in ALLOWED_FILE_EXTS:
        media_type = 'file'
    else:
        return JsonResponse(
            {'error': 'Unsupported file type. Allowed: images, PDF, Word, ZIP, TXT.'},
            status=400
        )

    user_id = request.POST.get('user_id')
    grp_id  = request.POST.get('group_id')

    if user_id:
        try:
            receiver = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found.'}, status=404)

        msg = Message.objects.create(
            sender=me, receiver=receiver,
            media=file, media_type=media_type,
        )
        return JsonResponse({
            'id':         msg.id,
            'media_url':  msg.media.url,
            'media_type': media_type,
            'file_name':  file.name,
            'sender_id':  me.pk,
            'sender_name': me.full_name,
            'timestamp':  msg.timestamp.isoformat(),
        })

    elif grp_id:
        try:
            group = ChatGroup.objects.get(pk=grp_id)
        except ChatGroup.DoesNotExist:
            return JsonResponse({'error': 'Group not found.'}, status=404)

        if not GroupMember.objects.filter(group=group, user=me).exists():
            return JsonResponse({'error': 'Not a member.'}, status=403)

        msg = GroupMessage.objects.create(
            group=group, sender=me,
            media=file, media_type=media_type,
        )
        return JsonResponse({
            'id':         msg.id,
            'media_url':  msg.media.url,
            'media_type': media_type,
            'file_name':  file.name,
            'sender_id':  me.pk,
            'sender_name': me.full_name,
            'timestamp':  msg.timestamp.isoformat(),
        })

    return JsonResponse({'error': 'Provide user_id or group_id.'}, status=400)


# ──────────────────────────────────────────────
# MEDIA GALLERY — all shared media in a DM
# ──────────────────────────────────────────────
@login_required
@require_GET
def media_gallery(request, user_id):
    me    = request.user
    other = get_object_or_404(User, pk=user_id)

    from django.core.paginator import Paginator
    media_qs = Message.objects.filter(
        Q(sender=me, receiver=other) | Q(sender=other, receiver=me)
    ).exclude(media='').order_by('-timestamp').select_related('sender')

    paginator = Paginator(media_qs, 24) # 24 per page
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    return render(request, 'chat/media_gallery.html', {
        'other':      other,
        'media_msgs': page_obj,
    })


# ──────────────────────────────────────────────
# GROUP MEDIA GALLERY
# ──────────────────────────────────────────────
@login_required
@require_GET
def group_media_gallery(request, group_id):
    me    = request.user
    group = get_object_or_404(ChatGroup, pk=group_id)

    if not GroupMember.objects.filter(group=group, user=me).exists():
        messages.error(request, 'Not a member.')
        return redirect('chat:group_list')

    from django.core.paginator import Paginator
    media_qs = GroupMessage.objects.filter(group=group).exclude(
        media=''
    ).order_by('-timestamp').select_related('sender')

    paginator = Paginator(media_qs, 24)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    return render(request, 'chat/group_media_gallery.html', {
        'group':      group,
        'media_msgs': page_obj,
    })


# ──────────────────────────────────────────────
# AI SUGGEST  (Phase 6 — Gemini powered)
# ──────────────────────────────────────────────
@login_required
@require_POST
def ai_suggest(request):
    try:
        data       = json.loads(request.body)
        context    = data.get('context', '').strip()
        other_name = data.get('other_name', 'them')
        msg_id     = data.get('last_msg_id')   # optional: fetch fresh context from DB
    except Exception:
        return JsonResponse({'error': 'Invalid request body.'}, status=400)

    # If JS didn't pass context, try fetching last 6 messages from DB
    if not context and msg_id:
        context = _fetch_context_from_db(request.user, msg_id)

    if not context:
        context = 'Start of conversation'

    try:
        from ai_assist.gemini import get_suggestion
        suggestion = get_suggestion(context, other_name)
    except Exception as e:
        logger.warning(f'ai_suggest fallback: {e}')
        from ai_assist.gemini import _mock_suggestion, detect_language
        lang       = detect_language(context)
        suggestion = _mock_suggestion(context, lang)

    return JsonResponse({'suggestion': suggestion})


@login_required
@require_POST
def schedule_message(request):
    try:
        data = json.loads(request.body)
        body = data.get('body', '').strip()
        time_str = data.get('scheduled_time') # ISO format
        user_id = data.get('user_id')
        group_id = data.get('group_id')

        if not body or not time_str:
            return JsonResponse({'error': 'Message and time are required.'}, status=400)

        scheduled_time = timezone.datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        
        if scheduled_time <= timezone.now():
            return JsonResponse({'error': 'Scheduled time must be in the future.'}, status=400)

        from scheduler.models import ScheduledMessage
        sm = ScheduledMessage.objects.create(
            sender=request.user,
            body=body,
            scheduled_time=scheduled_time,
            receiver_id=user_id if user_id else None,
            group_id=group_id if group_id else None
        )

        return JsonResponse({
            'success': True, 
            'id': sm.id,
            'message': f'Message scheduled for {scheduled_time.strftime("%Y-%m-%d %H:%M")}'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_GET
def list_scheduled_messages(request):
    from scheduler.models import ScheduledMessage
    msgs = ScheduledMessage.objects.filter(
        sender=request.user,
        is_sent=False,
        scheduled_time__gt=timezone.now()
    ).select_related('receiver', 'group')
    
    results = []
    for m in msgs:
        results.append({
            'id': m.id,
            'body': m.body,
            'scheduled_time': m.scheduled_time.isoformat(),
            'target_name': m.receiver.username if m.receiver else m.group.name,
            'is_group': bool(m.group)
        })
    return JsonResponse({'results': results})


@login_required
@require_POST
def cancel_scheduled_message(request, msg_id):
    from scheduler.models import ScheduledMessage
    sm = get_object_or_404(ScheduledMessage, pk=msg_id, sender=request.user, is_sent=False)
    sm.delete()
    return JsonResponse({'success': True})


@login_required
@require_GET
def search_users(request):
    query = request.GET.get('q', '').strip().lower()
    if not query:
        return JsonResponse({'results': []})

    # Search by username or full name
    users = User.objects.filter(
        Q(username__icontains=query) | Q(full_name__icontains=query)
    ).filter(is_active=True, is_verified=True).exclude(pk=request.user.pk)[:10]

    results = []
    for u in users:
        results.append({
            'id':        u.pk,
            'username':  u.username,
            'full_name': u.full_name,
            'avatar':    u.avatar.url if u.avatar else None,
        })

    return JsonResponse({'results': results})


def _fetch_context_from_db(user, last_msg_id):
    """Pull last 6 message bodies for context when JS can't."""
    try:
        from chat.models import Message
        from django.db.models import Q
        msgs = Message.objects.filter(
            Q(sender=user) | Q(receiver=user),
            id__lte=last_msg_id,
        ).order_by('-timestamp')[:6]
        parts = [m.body for m in reversed(msgs) if m.body]
        return ' | '.join(parts)
    except Exception:
        return 


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def _build_conversations(me):
    """
    Optimized: Fetches all users you've chatted with and their latest message
    in a single efficient query.
    """
    from django.db.models import OuterRef, Subquery, Max

    # Subquery to find the ID of the last message between 'me' and 'other'
    last_msg_sq = Message.objects.filter(
        Q(sender=me, receiver=OuterRef('pk')) | Q(sender=OuterRef('pk'), receiver=me)
    ).order_by('-timestamp').values('id')[:1]

    # Find users who have either sent or received a message from 'me'
    sent_to = Message.objects.filter(sender=me).values_list('receiver_id', flat=True)
    received_from = Message.objects.filter(receiver=me).values_list('sender_id', flat=True)
    talked_to_ids = set(list(sent_to) + list(received_from))

    if not talked_to_ids:
        return []

    # Fetch users with their last message pre-fetched
    users = User.objects.filter(pk__in=talked_to_ids, is_active=True).annotate(
        last_msg_id=Subquery(last_msg_sq)
    ).select_related('avatar') # Assuming avatar is a field, not a separate table

    # Get the actual message objects for the IDs found
    msg_ids = [u.last_msg_id for u in users if u.last_msg_id]
    msgs_map = {m.id: m for m in Message.objects.filter(id__in=msg_ids)}

    result = []
    for u in users:
        result.append({
            'user': u,
            'last_msg': msgs_map.get(u.last_msg_id)
        })

    # Sort by message timestamp
    result.sort(
        key=lambda c: c['last_msg'].timestamp if c['last_msg'] else timezone.now(),
        reverse=True,
    )
    return result


def _unread_counts(me):
    """Optimized unread count aggregation."""
    from django.db.models import Count
    return dict(
        Message.objects.filter(receiver=me, is_read=False)
        .values_list('sender_id')
        .annotate(cnt=Count('id'))
    )
