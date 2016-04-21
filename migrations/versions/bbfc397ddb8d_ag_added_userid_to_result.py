"""AG - added userid to result

Revision ID: bbfc397ddb8d
Revises: e9c2534d2a01
Create Date: 2016-04-21 02:24:05.458312

"""

# revision identifiers, used by Alembic.
revision = 'bbfc397ddb8d'
down_revision = 'e9c2534d2a01'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('results', sa.Column('userid', sa.Integer(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('results', 'userid')
    ### end Alembic commands ###
