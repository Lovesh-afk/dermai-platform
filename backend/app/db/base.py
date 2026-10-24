"""Import all models here so Alembic autogenerate can discover them
via Base.metadata — models themselves never import this file."""
from app.db.base_class import Base  # noqa
from app.models.appointment import Appointment  # noqa
from app.models.availability import DoctorAvailability  # noqa
from app.models.chat import ChatConversation, ChatMessage  # noqa
from app.models.audit_log import AuditLog  # noqa
from app.models.doctor import Doctor  # noqa
from app.models.hospital import Hospital  # noqa
from app.models.medical_record import MedicalRecord  # noqa
from app.models.notification import Notification  # noqa
from app.models.password_reset_token import PasswordResetToken  # noqa
from app.models.patient import Patient  # noqa
from app.models.prediction import Prediction  # noqa
from app.models.role import Role  # noqa
from app.models.session import UserSession  # noqa
from app.models.skin_image import SkinImage  # noqa
from app.models.user import User  # noqa
