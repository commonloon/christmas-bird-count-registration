"""circles and circle_areas tables, seeded with Vancouver's existing config

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-30

"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


# Mirrors config/organization.py's module constants at the time of this migration.
VANCOUVER_CIRCLE = {
    'slug': 'vancouver',
    'name': 'Nature Vancouver',
    'website': 'https://naturevancouver.ca',
    'contact': 'info@naturevancouver.ca',
    'count_contact': 'cbc@naturevancouver.ca',
    'count_event_name': 'Vancouver Christmas Bird Count',
    'count_info_url': 'https://naturevancouver.ca/birding/vancouver-area-christmas-bird-count/',
    'from_email': 'cbc@naturevancouver.ca',
    'logo_path': '/static/icons/NV_logo.png',
    'test_recipient': 'birdcount@naturevancouver.ca',
    'display_timezone': 'America/Vancouver',
    'is_cbc': True,
    'count_experience_label': 'CBC Experience',
    'feeder_counter_label': 'Count birds at my home feeder',
    'notes_placeholder_example': 'I would prefer to be assigned to an area in East Vancouver',
    'yearly_count_dates': {
        '2024': '2024-12-14',
        '2025': '2025-12-20',
        '2026': '2026-12-19',
        '2027': '2027-12-18',
        '2028': '2028-12-16',
        '2029': '2029-12-15',
    },
    'registration_opens_months': 4,
    'registration_closes_days': 1,
}

# Mirrors config/areas.py's AREA_CONFIG at the time of this migration.
VANCOUVER_AREAS = {
    'A': {'name': 'North Shore Uplands - West', 'description': 'West of the Capilano River, North of the Trans Canada Highway', 'difficulty': 'Moderate', 'terrain': 'Mountainous, some trails'},
    'B': {'name': 'Ambleside/West Van Coastal', 'description': 'South of Trans Canada, West of Capilano Road, marine boundary', 'difficulty': 'Easy', 'terrain': 'Coastal, urban parks'},
    'C': {'name': 'North Shore Uplands - Capilano to Lynn Creek', 'description': 'North of Trans Canada Highway between Lynn Creek and Capilano River', 'difficulty': 'Moderate', 'terrain': 'Forested, residential'},
    'D': {'name': 'North Vancouver East', 'description': 'South of Trans Canada Highway, east from Capilano Rd', 'difficulty': 'Easy', 'terrain': 'Urban, waterfront'},
    'E': {'name': 'Seymour to Cates Park, plus uplands', 'description': 'East from Lynn Creek, north from Burrard Inlet midpoint', 'difficulty': 'Moderate', 'terrain': 'Hillside residential, parks'},
    'F': {'name': 'Burnaby North', 'description': 'East from Trans Canada, north from Lougheed to Burrard Inlet', 'difficulty': 'Moderate', 'terrain': 'University, conservation area'},
    'G': {'name': 'Burnaby Central', 'description': 'Between Lougheed Highway and Kingsway, east of Boundary Road', 'difficulty': 'Easy', 'terrain': 'Suburban residential'},
    'H': {'name': 'Burnaby South', 'description': 'North from Fraser River midpoint, east from Boundary Road', 'difficulty': 'Easy', 'terrain': 'Urban, riverfront'},
    'I': {'name': 'East Vancouver - South', 'description': 'North from Fraser River, between Fraser Street and Boundary Road', 'difficulty': 'Easy', 'terrain': 'Industrial, residential'},
    'J': {'name': 'East Vancouver - Trout Lake', 'description': 'West from Boundary Road, between Broadway and 41st Avenue', 'difficulty': 'Easy', 'terrain': 'Dense residential'},
    'K': {'name': 'East Vancouver - North', 'description': 'North from Broadway, between Main Street and Boundary Road', 'difficulty': 'Easy', 'terrain': 'Urban, light industrial'},
    'L': {'name': 'Downtown Vancouver', 'description': 'Downtown core plus False Creek Flats, marine boundaries', 'difficulty': 'Easy', 'terrain': 'Dense urban, waterfront'},
    'M': {'name': 'Cambie Corridor - QE Park/VanDusen', 'description': 'East from Granville, between 7th Avenue and Kingsway', 'difficulty': 'Easy', 'terrain': 'Dense residential, transit corridor'},
    'N': {'name': 'Cambie Corridor - South', 'description': 'South from 41st Avenue between Granville and Fraser River', 'difficulty': 'Easy', 'terrain': 'Suburban, some industrial'},
    'O': {'name': 'Marpole/Southlands', 'description': 'South from 33rd between Granville and Camosun to Fraser River', 'difficulty': 'Easy', 'terrain': 'Residential, airport vicinity'},
    'P': {'name': 'Kitsilano/Jericho', 'description': 'Central Vancouver, marine boundary considerations', 'difficulty': 'Easy', 'terrain': 'Dense residential, beaches'},
    'Q': {'name': 'UBC North', 'description': 'West from Blanca, north from W 16th Avenue, marine boundaries', 'difficulty': 'Moderate', 'terrain': 'Beaches, parks, residential'},
    'R': {'name': 'UBC South/Musqueam', 'description': 'University and endowment lands, Musqueam territory', 'difficulty': 'Moderate', 'terrain': 'University campus, forest, beach'},
    'S': {'name': 'Iona', 'description': 'South shore areas with marine boundaries', 'difficulty': 'Moderate', 'terrain': 'Riverfront, mixed development'},
    'T': {'name': 'Airport and surrounds', 'description': 'Vancouver International Airport and surrounds', 'difficulty': 'Easy', 'terrain': 'Airport and surrounds'},
    'U': {'name': 'Northwest Richmond', 'description': 'Central Richmond areas', 'difficulty': 'Easy', 'terrain': 'Suburban, agricultural'},
    'V': {'name': 'Northeast Richmond', 'description': 'Richmond east of Number 5 Road, river counting coordination needed', 'difficulty': 'Easy', 'terrain': 'Agricultural, bog areas'},
    'W': {'name': 'Stanley Park West', 'description': 'Stanley Park and surrounding marine areas', 'difficulty': 'Easy', 'terrain': 'Urban park, seawall, beaches'},
    'X': {'name': 'Stanley Park East', 'description': 'North and east from Stanley Park Causeway, marine boundaries', 'difficulty': 'Easy', 'terrain': 'Urban waterfront, marinas'},
    'Y': {'name': 'Burrard Inlet/English Bay', 'description': 'This area is counted from one or more boats', 'difficulty': 'Moderate', 'terrain': 'Marine, boat-based counting'},
}


def upgrade():
    op.create_table(
        'circles',
        sa.Column('slug', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('website', sa.String(500)),
        sa.Column('contact', sa.String(254)),
        sa.Column('count_contact', sa.String(254)),
        sa.Column('count_event_name', sa.String(200)),
        sa.Column('count_info_url', sa.String(500)),
        sa.Column('from_email', sa.String(254)),
        sa.Column('logo_path', sa.String(500)),
        sa.Column('test_recipient', sa.String(254)),
        sa.Column('display_timezone', sa.String(100), nullable=False, server_default='America/Vancouver'),
        sa.Column('is_cbc', sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column('count_experience_label', sa.String(200)),
        sa.Column('feeder_counter_label', sa.String(200)),
        sa.Column('notes_placeholder_example', sa.Text),
        sa.Column('yearly_count_dates', sa.JSON, nullable=False),
        sa.Column('registration_opens_months', sa.Integer, nullable=False, server_default='4'),
        sa.Column('registration_closes_days', sa.Integer, nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'circle_areas',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('circle_slug', sa.String(50), sa.ForeignKey('circles.slug'), nullable=False),
        sa.Column('code', sa.String(10), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('difficulty', sa.String(50)),
        sa.Column('terrain', sa.String(200)),
        sa.UniqueConstraint('circle_slug', 'code', name='uq_circle_areas_circle_code'),
    )
    op.create_index('ix_circle_areas_circle_slug', 'circle_areas', ['circle_slug'])

    now = datetime.now(timezone.utc)

    circles_table = sa.table(
        'circles',
        sa.column('slug', sa.String),
        sa.column('name', sa.String),
        sa.column('website', sa.String),
        sa.column('contact', sa.String),
        sa.column('count_contact', sa.String),
        sa.column('count_event_name', sa.String),
        sa.column('count_info_url', sa.String),
        sa.column('from_email', sa.String),
        sa.column('logo_path', sa.String),
        sa.column('test_recipient', sa.String),
        sa.column('display_timezone', sa.String),
        sa.column('is_cbc', sa.Boolean),
        sa.column('count_experience_label', sa.String),
        sa.column('feeder_counter_label', sa.String),
        sa.column('notes_placeholder_example', sa.Text),
        sa.column('yearly_count_dates', sa.JSON),
        sa.column('registration_opens_months', sa.Integer),
        sa.column('registration_closes_days', sa.Integer),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )
    op.bulk_insert(circles_table, [{
        **VANCOUVER_CIRCLE,
        'created_at': now,
        'updated_at': now,
    }])

    circle_areas_table = sa.table(
        'circle_areas',
        sa.column('circle_slug', sa.String),
        sa.column('code', sa.String),
        sa.column('name', sa.String),
        sa.column('description', sa.Text),
        sa.column('difficulty', sa.String),
        sa.column('terrain', sa.String),
    )
    op.bulk_insert(circle_areas_table, [
        {
            'circle_slug': 'vancouver',
            'code': code,
            'name': info['name'],
            'description': info['description'],
            'difficulty': info['difficulty'],
            'terrain': info['terrain'],
        }
        for code, info in VANCOUVER_AREAS.items()
    ])


def downgrade():
    op.drop_table('circle_areas')
    op.drop_table('circles')
