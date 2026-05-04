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

from .models import Message, ChatGroup, GroupMember, GroupMessage

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
    all_users     = User.objects.exclude(pk=me.pk).filter(is_active=True, is_verified=True)
    my_groups     = ChatGroup.objects.filter(members__user=me).prefetch_related('members')
    conversations = _build_conversations(me, all_users)
    return render(request, 'chat/index.html', {
        'conversations': conversations,
        'all_users':     all_users,
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

    all_users     = User.objects.exclude(pk=me.pk).filter(is_active=True, is_verified=True)
    my_groups     = ChatGroup.objects.filter(members__user=me)
    conversations = _build_conversations(me, all_users)

    return render(request, 'chat/room.html', {
        'other':         other,
        'history':       history,
        'conversations': conversations,
        'all_users':     all_users,
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
    all_users     = User.objects.exclude(pk=me.pk).filter(is_active=True, is_verified=True)
    conversations = _build_conversations(me, all_users)
    return render(request, 'chat/group_list.html', {
        'my_groups':     my_groups,
        'all_users':     all_users,
        'conversations': conversations,
    })


# ──────────────────────────────────────────────
# CREATE GROUP
# ──────────────────────────────────────────────
@login_required
def create_group(request):
    me        = request.user
    all_users = User.objects.exclude(pk=me.pk).filter(is_active=True, is_verified=True)

    if request.method == 'POST':
        name        = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        member_ids  = request.POST.getlist('members')

        if not name:
            messages.error(request, 'Group name is required.')
            return render(request, 'chat/create_group.html', {'all_users': all_users})

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

    return render(request, 'chat/create_group.html', {'all_users': all_users})


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
    all_users = User.objects.exclude(pk=me.pk).filter(is_active=True, is_verified=True)
    my_groups = ChatGroup.objects.filter(members__user=me)
    conversations = _build_conversations(me, all_users)

    # Users not already in group (for add member dropdown)
    member_user_ids    = members.values_list('user_id', flat=True)
    non_members        = all_users.exclude(pk__in=member_user_ids)

    return render(request, 'chat/group_room.html', {
        'group':        group,
        'history':      history,
        'members':      members,
        'membership':   membership,
        'non_members':  non_members,
        'conversations': conversations,
        'all_users':    all_users,
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

    media_msgs = Message.objects.filter(
        Q(sender=me, receiver=other) | Q(sender=other, receiver=me)
    ).exclude(media='').order_by('-timestamp').select_related('sender')

    return render(request, 'chat/media_gallery.html', {
        'other':      other,
        'media_msgs': media_msgs,
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

    media_msgs = GroupMessage.objects.filter(group=group).exclude(
        media=''
    ).order_by('-timestamp').select_related('sender')

    return render(request, 'chat/group_media_gallery.html', {
        'group':      group,
        'media_msgs': media_msgs,
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


def _fetch_context_from_db(user, last_msg_id):
    """Pull last 6 message bodies for context when JS can't."""
    try:
        from .models import Message
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
def _build_conversations(me, all_users):
    chatted = Message.objects.filter(
        Q(sender=me) | Q(receiver=me)
    ).values_list('sender_id', 'receiver_id')

    talked_to = set()
    for s, r in chatted:
        talked_to.add(r if s == me.pk else s)

    result = []
    for uid in talked_to:
        try:
            other = all_users.get(pk=uid)
        except User.DoesNotExist:
            continue
        last_msg = Message.objects.filter(
            Q(sender=me, receiver=other) | Q(sender=other, receiver=me)
        ).order_by('-timestamp').first()
        result.append({'user': other, 'last_msg': last_msg})

    result.sort(
        key=lambda c: c['last_msg'].timestamp if c['last_msg'] else timezone.now(),
        reverse=True,
    )
    return result


def _unread_counts(me):
    """Return {user_id: unread_count} for sidebar badges."""
    from django.db.models import Count
    rows = Message.objects.filter(
        receiver=me, is_read=False
    ).values('sender_id').annotate(cnt=Count('id'))
    return {r['sender_id']: r['cnt'] for r in rows}
