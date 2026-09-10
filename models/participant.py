from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging

from sqlalchemy.exc import IntegrityError

from models.db import Participant, resolve_default_circle_slug


class DuplicateParticipantError(Exception):
    """Raised when a (circle_slug, year, first_name, last_name, email) identity
    already exists - normally caught earlier by the callers' own
    email_name_exists()/get_participant_by_email_and_names() pre-check, so
    reaching this is the rare race between two near-simultaneous submissions
    with the same identity, not the expected path."""
    pass


class ParticipantModel:
    """Handle PostgreSQL operations for participants, scoped by year (and circle_slug for
    future multi-circle support - see the multi-circle-architecture note)."""

    def __init__(self, db_session, year: int = None, circle_slug: str = None):
        self.db = db_session
        self.year = year or datetime.now().year
        self.circle_slug = circle_slug or resolve_default_circle_slug()
        self.logger = logging.getLogger(__name__)

    def _base_query(self):
        return self.db.query(Participant).filter_by(year=self.year, circle_slug=self.circle_slug)

    def add_participant(self, participant_data: Dict) -> int:
        """Add a new participant to the year/circle scope."""
        now = datetime.now(timezone.utc)

        participant = Participant(
            year=self.year,
            circle_slug=self.circle_slug,
            first_name=participant_data.get('first_name'),
            last_name=participant_data.get('last_name'),
            email=(participant_data.get('email') or '').lower(),
            phone=participant_data.get('phone'),
            phone2=participant_data.get('phone2'),
            preferred_area=participant_data.get('preferred_area'),
            status=participant_data.get('status', 'active'),
            skill_level=participant_data.get('skill_level'),
            experience=participant_data.get('experience'),
            participation_type=participant_data.get('participation_type', 'regular'),
            is_leader=participant_data.get('is_leader', False),
            assigned_area_leader=participant_data.get('assigned_area_leader'),
            leadership_assigned_by=participant_data.get('leadership_assigned_by'),
            leadership_assigned_at=participant_data.get('leadership_assigned_at'),
            leadership_removed_by=participant_data.get('leadership_removed_by'),
            leadership_removed_at=participant_data.get('leadership_removed_at'),
            has_binoculars=participant_data.get('has_binoculars', False),
            spotting_scope=participant_data.get('spotting_scope', False),
            interested_in_leadership=participant_data.get('interested_in_leadership', False),
            notes_to_organizers=participant_data.get('notes_to_organizers', ''),
            created_at=now,
            updated_at=now,
        )
        self.db.add(participant)
        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            if 'uq_participants_identity' in str(e.orig):
                raise DuplicateParticipantError(
                    f"A participant with identity ({participant.first_name}, "
                    f"{participant.last_name}, {participant.email}) already exists "
                    f"for {self.circle_slug} {self.year}."
                ) from e
            raise
        self.logger.info(f"Added participant to year {self.year}: {participant.email}")
        return participant.id

    def get_participant(self, participant_id) -> Optional[Dict]:
        """Get a participant by ID, scoped to this year/circle."""
        try:
            participant_id = int(participant_id)
        except (TypeError, ValueError):
            return None
        participant = self._base_query().filter_by(id=participant_id).first()
        return participant.to_dict() if participant else None

    def get_participants_by_area(self, area_code: str) -> List[Dict]:
        """Get all active participants for a specific area in the current year."""
        rows = self._base_query().filter_by(status='active', preferred_area=area_code).all()
        return [r.to_dict() for r in rows]

    def get_withdrawn_participants_by_area(self, area_code: str) -> List[Dict]:
        """Get all withdrawn participants for a specific area in the current year."""
        rows = self._base_query().filter_by(status='withdrawn', preferred_area=area_code).all()
        return [r.to_dict() for r in rows]

    def get_unassigned_participants(self) -> List[Dict]:
        """Get all active participants with preferred_area = 'UNASSIGNED'."""
        rows = self._base_query().filter_by(status='active', preferred_area='UNASSIGNED').all()
        return [r.to_dict() for r in rows]

    def assign_participant_to_area(self, participant_id, area_code: str, assigned_by: str) -> bool:
        """Assign an unassigned participant to a specific area."""
        try:
            participant = self._base_query().filter_by(id=int(participant_id)).first()
            if not participant:
                return False
            participant.preferred_area = area_code
            participant.updated_at = datetime.now(timezone.utc)
            participant.assigned_by = assigned_by
            participant.assigned_at = datetime.now(timezone.utc)
            self.db.commit()
            self.logger.info(f"Assigned participant {participant_id} to area {area_code}")
            return True
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Failed to assign participant {participant_id}: {e}")
            return False

    def get_area_counts(self) -> Dict[str, int]:
        """Get active participant count by area for the current year."""
        counts = {}
        rows = self._base_query().filter_by(status='active').all()
        for row in rows:
            area = row.preferred_area or 'UNKNOWN'
            if area != 'UNASSIGNED':
                counts[area] = counts.get(area, 0) + 1
        return counts

    def get_participants_by_email(self, email: str) -> List[Dict]:
        """Get all participants with a specific email address."""
        rows = self._base_query().filter_by(email=email.lower()).all()
        return [r.to_dict() for r in rows]

    def get_participant_by_email_and_names(self, email: str, first_name: str, last_name: str) -> Optional[Dict]:
        """Get participant by exact email + first_name + last_name match."""
        row = self._base_query().filter_by(
            email=email.lower(), first_name=first_name, last_name=last_name
        ).first()
        return row.to_dict() if row else None

    def update_participant(self, participant_id, updates: Dict) -> bool:
        """Update a participant's information."""
        try:
            participant = self._base_query().filter_by(id=int(participant_id)).first()
            if not participant:
                return False
            for key, value in updates.items():
                if hasattr(participant, key):
                    setattr(participant, key, value)
            participant.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Failed to update participant {participant_id}: {e}")
            return False

    def delete_participant(self, participant_id, commit=True) -> bool:
        """Delete a participant (single table - no synchronization needed).

        commit=False lets a caller compose this into a larger atomic
        operation (e.g. delete + log_removal + deactivate_leaders_by_identity
        as one transaction - see routes/admin.py's delete_participant route)
        - flushes instead of committing, and lets an exception propagate to
        the caller's own try/except+rollback rather than catching and rolling
        back here, which would also discard the caller's other
        not-yet-committed work in the same transaction."""
        def _do():
            participant = self._base_query().filter_by(id=int(participant_id)).first()
            if not participant:
                self.logger.error(f"Participant {participant_id} not found for deletion")
                return False
            self.db.delete(participant)
            if commit:
                self.db.commit()
            else:
                self.db.flush()
            self.logger.info(f"Deleted participant {participant_id} from year {self.year}")
            return True

        if not commit:
            return _do()
        try:
            return _do()
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Failed to delete participant {participant_id}: {e}")
            return False

    def get_all_participants(self) -> List[Dict]:
        """Get all participants for the current year."""
        rows = self._base_query().order_by(Participant.created_at.desc()).all()
        return [r.to_dict() for r in rows]

    def email_exists(self, email: str) -> bool:
        """Check if an email is already registered for the current year."""
        return self._base_query().filter_by(email=email.lower()).first() is not None

    def email_name_exists(self, email: str, first_name: str, last_name: str) -> bool:
        """Check if email+name combination exists for current year."""
        return self.get_participant_by_email_and_names(email, first_name, last_name) is not None

    def get_participants_interested_in_leadership(self) -> List[Dict]:
        """Get active participants who expressed interest in leadership but aren't assigned as leaders."""
        rows = self._base_query().filter_by(
            status='active', interested_in_leadership=True, is_leader=False
        ).all()
        return [r.to_dict() for r in rows]

    def get_historical_participants(self, area_code: str, years_back: int = 3) -> List[Dict]:
        """Get participants for an area across multiple years, with email deduplication."""
        current_year = datetime.now().year
        participants = {}  # email -> most recent participant data

        for year in range(current_year - years_back, current_year + 1):
            try:
                year_model = ParticipantModel(self.db, year, self.circle_slug)
                year_participants = year_model.get_participants_by_area(area_code)

                for participant in year_participants:
                    email = (participant.get('email') or '').lower()
                    if email:
                        participants[email] = participant
            except Exception as e:
                self.logger.warning(f"Could not access participants for year {year}: {e}")
                continue

        return list(participants.values())

    def get_leaders(self) -> List[Dict]:
        """Get all active leaders for the current year."""
        rows = self._base_query().filter_by(is_leader=True).all()
        return [r.to_dict() for r in rows]

    def get_leaders_by_area(self, area_code: str) -> List[Dict]:
        """Get all active leaders for a specific area."""
        rows = self._base_query().filter_by(is_leader=True, assigned_area_leader=area_code).all()
        return [r.to_dict() for r in rows]

    def is_area_leader(self, email: str, area_code: str = None) -> bool:
        """Check if an email is an area leader (optionally for a specific area)."""
        query = self._base_query().filter_by(is_leader=True, email=email.lower())
        if area_code is not None:
            query = query.filter_by(assigned_area_leader=area_code)
        return query.first() is not None

    def get_leaders_by_identity(self, first_name: str, last_name: str, email: str) -> List[Dict]:
        """Get all leaders matching exact identity (first_name, last_name, email)."""
        rows = self._base_query().filter_by(
            is_leader=True,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=email.lower().strip(),
        ).all()
        return [r.to_dict() for r in rows]

    def get_areas_without_leaders(self) -> List[str]:
        """Get list of area codes that don't have assigned leaders."""
        # Deliberately not config/areas.py's get_all_areas() - that reads the
        # *ambient* Flask g.circle_slug (raises without one), which may not even
        # be running inside a request at all, let alone one resolved to this
        # model's own self.circle_slug. Query this circle's areas directly instead.
        from models.circle import CircleAreaModel

        all_areas = {a['code'] for a in CircleAreaModel(self.db).get_areas_for_circle(self.circle_slug)}
        assigned_areas = {
            leader.get('assigned_area_leader')
            for leader in self.get_leaders()
            if leader.get('assigned_area_leader')
        }
        return sorted(all_areas - assigned_areas)

    def assign_area_leadership(self, participant_id, area_code: str, assigned_by: str) -> bool:
        """Assign area leadership to a participant."""
        try:
            participant = self._base_query().filter_by(id=int(participant_id)).first()
            if not participant:
                return False
            now = datetime.now(timezone.utc)
            participant.is_leader = True
            participant.assigned_area_leader = area_code
            participant.preferred_area = area_code
            participant.leadership_assigned_by = assigned_by
            participant.leadership_assigned_at = now
            participant.updated_at = now
            self.db.commit()
            self.logger.info(f"Assigned area leadership of {area_code} to participant {participant_id}")
            return True
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Failed to assign area leadership: {e}")
            return False

    def remove_area_leadership(self, participant_id, removed_by: str, commit=True) -> bool:
        """Remove area leadership from a participant. commit=False composes
        into a larger atomic operation - see delete_participant's docstring."""
        def _do():
            participant = self._base_query().filter_by(id=int(participant_id)).first()
            if not participant:
                return False
            now = datetime.now(timezone.utc)
            participant.is_leader = False
            participant.assigned_area_leader = None
            participant.leadership_removed_by = removed_by
            participant.leadership_removed_at = now
            participant.updated_at = now
            if commit:
                self.db.commit()
            else:
                self.db.flush()
            self.logger.info(f"Removed area leadership from participant {participant_id}")
            return True

        if not commit:
            return _do()
        try:
            return _do()
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Failed to remove area leadership: {e}")
            return False

    def deactivate_leaders_by_identity(self, first_name: str, last_name: str, email: str, removed_by: str,
                                        commit=True) -> bool:
        """Deactivate all leaders matching exact identity (first_name, last_name, email).
        commit=False composes into a larger atomic operation - see
        delete_participant's docstring. With commit=False, an exception from
        remove_area_leadership propagates rather than being caught here, so
        the composite caller's own rollback covers this step too."""
        def _do():
            matching_leaders = self.get_leaders_by_identity(first_name, last_name, email)
            if not matching_leaders:
                self.logger.info(f"No active leaders found for identity: {first_name} {last_name} <{email}>")
                return True

            for leader in matching_leaders:
                if not self.remove_area_leadership(leader['id'], removed_by, commit=commit):
                    if commit:
                        self.logger.error(f"Failed to deactivate leader {leader['id']} for {first_name} {last_name}")
                        return False
                    # commit=False: a False return (not an exception) here means
                    # the leader row genuinely wasn't found - already an
                    # inconsistent identity snapshot, not something a retry
                    # would fix, so surface it the same way instead of silently
                    # continuing.
                    raise RuntimeError(
                        f"Failed to deactivate leader {leader['id']} for {first_name} {last_name} - row not found")

            self.logger.info(f"Successfully deactivated {len(matching_leaders)} leader(s) for {first_name} {last_name} <{email}>")
            return True

        if not commit:
            return _do()
        try:
            return _do()
        except Exception as e:
            self.logger.error(f"Failed to deactivate leaders by identity {first_name} {last_name} <{email}>: {e}")
            return False

    def add_leader(self, leader_data: Dict) -> str:
        """Add a new participant with leadership role. Returns participant ID or raises exception if identity exists."""
        first_name = leader_data.get('first_name', '')
        last_name = leader_data.get('last_name', '')
        email = leader_data.get('email', '')

        existing = self.get_participant_by_email_and_names(email, first_name, last_name)
        if existing:
            raise ValueError(
                f"Participant with identity ({first_name}, {last_name}, {email}) already exists. "
                f"Use participant editing to update existing records."
            )

        participant_data = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email.lower(),
            'phone': leader_data.get('phone', ''),
            'phone2': leader_data.get('phone2', ''),
            'is_leader': True,
            'assigned_area_leader': leader_data.get('area_code'),
            'leadership_assigned_by': leader_data.get('assigned_by'),
            'leadership_assigned_at': datetime.now(timezone.utc),
            'preferred_area': leader_data.get('area_code'),
            'skill_level': leader_data.get('skill_level', 'Expert'),
            'experience': leader_data.get('experience', '3+ counts'),
            'participation_type': 'regular',
            'has_binoculars': leader_data.get('has_binoculars', False),
            'spotting_scope': leader_data.get('spotting_scope', False),
            'interested_in_leadership': True,
            'notes_to_organizers': leader_data.get('notes', ''),
        }
        return self.add_participant(participant_data)

    def remove_leader(self, participant_id, removed_by: str, commit=True) -> bool:
        """Remove leadership from a participant (wrapper for remove_area_leadership)."""
        return self.remove_area_leadership(participant_id, removed_by, commit=commit)

    def withdraw_participant(self, participant_id, commit=True) -> bool:
        """Withdraw a participant from the count, removing leadership if applicable
        (both on the same row, so already atomic with each other regardless of
        commit). commit=False composes into a larger atomic operation (e.g.
        withdraw + log_withdrawal as one transaction) - see
        delete_participant's docstring."""
        def _do():
            participant = self._base_query().filter_by(id=int(participant_id)).first()
            if not participant:
                self.logger.error(f"Participant {participant_id} not found for withdrawal")
                return False

            participant.status = 'withdrawn'
            participant.updated_at = datetime.now(timezone.utc)

            if participant.is_leader:
                participant.is_leader = False
                participant.assigned_area_leader = None
                participant.leadership_removed_by = 'system-withdrawal'
                participant.leadership_removed_at = datetime.now(timezone.utc)

            if commit:
                self.db.commit()
            else:
                self.db.flush()
            self.logger.info(f"Withdrew participant {participant_id} from year {self.year}")
            return True

        if not commit:
            return _do()
        try:
            return _do()
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Failed to withdraw participant {participant_id}: {e}")
            return False

    def reactivate_participant(self, participant_id, commit=True) -> bool:
        """Reactivate a withdrawn participant. commit=False composes into a
        larger atomic operation - see delete_participant's docstring."""
        def _do():
            participant = self._base_query().filter_by(id=int(participant_id)).first()
            if not participant:
                self.logger.error(f"Participant {participant_id} not found for reactivation")
                return False
            if participant.status != 'withdrawn':
                self.logger.warning(f"Participant {participant_id} is not withdrawn, cannot reactivate")
                return False

            participant.status = 'active'
            participant.updated_at = datetime.now(timezone.utc)
            if commit:
                self.db.commit()
            else:
                self.db.flush()
            self.logger.info(f"Reactivated participant {participant_id} in year {self.year}")
            return True

        if not commit:
            return _do()
        try:
            return _do()
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Failed to reactivate participant {participant_id}: {e}")
            return False

    def get_withdrawn_participants(self) -> List[Dict]:
        """Get all withdrawn participants for the current year."""
        rows = self._base_query().filter_by(status='withdrawn').all()
        return [r.to_dict() for r in rows]

    @classmethod
    def get_available_years(cls, db_session, circle_slug: str = None) -> List[int]:
        """Get the years selectable in the admin/leader year picker for a circle:
        every year with participant data, plus the current year even if it has none
        yet.

        circle_slug defaults via resolve_default_circle_slug() (the current request's
        circle, in a request context) - the participants table is shared across every
        circle, so an unfiltered query here would surface other circles' years as if
        they were this one's (confirmed: Comox Spring showed tabs back to 2023 despite
        having zero participants, because those years only ever existed for Vancouver/
        Ladner).

        Always including the current year matters because every caller (dashboard,
        participants list, leaders, area detail, recent registrations, leader
        dashboard) only shows its year selector when this returns more than one
        year - a circle whose only data is a single historical year (e.g. Nanaimo,
        freshly imported with only 2025 data and no 2026 registrations yet) would
        otherwise get back a length-1 list, hiding the selector entirely and
        stranding the admin on an empty current-year view with no way to reach the
        year that actually has data.
        """
        circle_slug = circle_slug or resolve_default_circle_slug()
        current_year = datetime.now().year
        try:
            years = {row[0] for row in db_session.query(Participant.year)
                     .filter_by(circle_slug=circle_slug).distinct().all()}
            years.add(current_year)
            return sorted(years, reverse=True)
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get available years: {e}")
            return [current_year]
