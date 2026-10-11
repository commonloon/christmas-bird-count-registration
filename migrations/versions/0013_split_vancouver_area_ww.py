"""Vancouver: split area W into W (south) and WW (north)

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-05

The old paper map divided Stanley Park into areas W and WW; the registration
site had them as a single area W. This updates W's boundary/description to the
southern half, and creates WW (the northern half) with its boundary/description.

Deliberately touches ONLY the vancouver circle's W and WW rows:
- participants / leaders already on W stay on W (admins move people by hand);
- W's name, difficulty and terrain are left as they are (WW copies W's difficulty/terrain);
- no other area, the circle row (lat/lng, boundary lines) or area_signup_type
  is changed - a missing area_signup_type row already means "open to public
  registration", which is what WW should be.

Geometry/text is embedded (not read from utils/Vancouver_CBC_Areas.kml at run
time) so this migration keeps working unchanged if that file is edited later.
Both helpers take the slug so tests can run them against the 'test' circle.

downgrade() restores the old single-polygon W, and removes WW only if no
participant or leader row references it (otherwise it refuses, rather than
orphaning those rows).
"""
from alembic import op
import sqlalchemy as sa

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None

CIRCLE_SLUG = 'vancouver'

NEW_W_DESCRIPTION = 'South Stanley Park, including Second Beach and Lost Lagoon, extending south to Denman St.'
NEW_WW_NAME = 'Stanley Park Northwest'
NEW_WW_DESCRIPTION = 'Stanley Park north of Lost Lagoon and West of the Causeway'
OLD_W_DESCRIPTION = (
    'West of the Stanley Park Causeway, North of Denman.  Marine boundary extends to approx 200m '
    'offshore: negotiate with leaders of areas B, Y, L and P how to handle the marine boundaries.'
)

NEW_W_GEOMETRY = {'type': 'Polygon', 'coordinates': [[
    [-123.1393099, 49.2985719],
    [-123.1412745, 49.2995429],
    [-123.1448436, 49.2994324],
    [-123.1456233, 49.2993178],
    [-123.151654, 49.2992031],
    [-123.1578862, 49.2993446],
    [-123.1690729, 49.299301],
    [-123.1691232, 49.2981603],
    [-123.16569, 49.2932344],
    [-123.1485238, 49.2829894],
    [-123.1334176, 49.2925627],
    [-123.1368508, 49.2946339],
    [-123.1363359, 49.2959213],
    [-123.1364217, 49.2968729],
    [-123.1371546, 49.2976959],
    [-123.1393099, 49.2985719],
]]}
NEW_WW_GEOMETRY = {'type': 'Polygon', 'coordinates': [[
    [-123.1443954, 49.2994604],
    [-123.1412745, 49.2995429],
    [-123.1423474, 49.3002006],
    [-123.143828, 49.3014179],
    [-123.1448043, 49.3028241],
    [-123.1453407, 49.3049998],
    [-123.144933, 49.3073922],
    [-123.1436992, 49.3097495],
    [-123.1389966, 49.314921],
    [-123.1486225, 49.3192789],
    [-123.1539311, 49.3177466],
    [-123.1600251, 49.3150609],
    [-123.1659474, 49.3096891],
    [-123.1690373, 49.3025818],
    [-123.1691447, 49.2993287],
    [-123.1578862, 49.2993446],
    [-123.151654, 49.2992031],
    [-123.1512237, 49.2992295],
    [-123.1505406, 49.2992555],
    [-123.1498682, 49.2992598],
    [-123.148892, 49.2992816],
    [-123.1466627, 49.2993042],
    [-123.1456233, 49.2993178],
    [-123.1448436, 49.2994324],
    [-123.1443954, 49.2994604],
]]}

OLD_W_GEOMETRY = {'type': 'Polygon', 'coordinates': [[
    [-123.1389966, 49.314921],
    [-123.1486955, 49.3192572],
    [-123.1539311, 49.3177466],
    [-123.1600251, 49.3150609],
    [-123.1659474, 49.3096891],
    [-123.1690373, 49.3025818],
    [-123.1691232, 49.2981043],
    [-123.16569, 49.2932344],
    [-123.1485238, 49.2829894],
    [-123.1334176, 49.2925627],
    [-123.1350484, 49.2935703],
    [-123.1368508, 49.2946339],
    [-123.1363359, 49.2959213],
    [-123.1364217, 49.2968729],
    [-123.1379666, 49.2979923],
    [-123.1402841, 49.2989438],
    [-123.1422582, 49.3002871],
    [-123.1442752, 49.3020501],
    [-123.1453481, 49.3051003],
    [-123.1448331, 49.3075627],
    [-123.1436315, 49.3097451],
    [-123.1420865, 49.3114798],
    [-123.1389966, 49.314921],
]]}


_circle_areas = sa.table(
    'circle_areas',
    sa.column('circle_slug', sa.String),
    sa.column('code', sa.String),
    sa.column('name', sa.String),
    sa.column('description', sa.Text),
    sa.column('boundary_geojson', sa.JSON),
    sa.column('difficulty', sa.String),
    sa.column('terrain', sa.String),
)
_participants = sa.table(
    'participants',
    sa.column('circle_slug', sa.String),
    sa.column('preferred_area', sa.String),
    sa.column('assigned_area_leader', sa.String),
)


def split_w(connection, slug=CIRCLE_SLUG):
    """Update W to the southern half and create WW. Raises if the circle has no W
    (nothing sensible to split), or already has a WW (never overwrite one)."""
    w_row = connection.execute(
        sa.select(_circle_areas.c.difficulty, _circle_areas.c.terrain)
        .where(_circle_areas.c.circle_slug == slug, _circle_areas.c.code == 'W')
    ).fetchone()
    if w_row is None:
        raise RuntimeError(f"circle '{slug}' has no area W to split")
    ww_rows = connection.execute(
        sa.select(_circle_areas.c.code).where(_circle_areas.c.circle_slug == slug, _circle_areas.c.code == 'WW')
    ).fetchall()
    if ww_rows:
        raise RuntimeError(f"circle '{slug}' already has an area WW")

    connection.execute(
        _circle_areas.update()
        .where(_circle_areas.c.circle_slug == slug, _circle_areas.c.code == 'W')
        .values(description=NEW_W_DESCRIPTION, boundary_geojson=NEW_W_GEOMETRY)
    )
    connection.execute(
        _circle_areas.insert().values(
            circle_slug=slug, code='WW', name=NEW_WW_NAME,
            description=NEW_WW_DESCRIPTION, boundary_geojson=NEW_WW_GEOMETRY,
            difficulty=w_row.difficulty, terrain=w_row.terrain,  # unused labels; same as W
        )
    )


def merge_ww_into_w(connection, slug=CIRCLE_SLUG):
    in_use = connection.execute(
        sa.select(sa.func.count()).select_from(_participants).where(
            _participants.c.circle_slug == slug,
            sa.or_(_participants.c.preferred_area == 'WW', _participants.c.assigned_area_leader == 'WW'),
        )
    ).scalar()
    if in_use:
        raise RuntimeError(f"{in_use} participant row(s) in '{slug}' still reference area WW; reassign them before downgrading")

    connection.execute(
        _circle_areas.update()
        .where(_circle_areas.c.circle_slug == slug, _circle_areas.c.code == 'W')
        .values(description=OLD_W_DESCRIPTION, boundary_geojson=OLD_W_GEOMETRY)
    )
    connection.execute(
        _circle_areas.delete().where(_circle_areas.c.circle_slug == slug, _circle_areas.c.code == 'WW')
    )


def upgrade():
    connection = op.get_bind()
    circles = sa.table('circles', sa.column('slug', sa.String))
    if not connection.execute(sa.select(circles.c.slug).where(circles.c.slug == CIRCLE_SLUG)).fetchone():
        return  # a database without the Vancouver circle has nothing to split
    split_w(connection)


def downgrade():
    merge_ww_into_w(op.get_bind())
