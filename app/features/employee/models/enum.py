from enum import Enum
 
 
class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"
 
 
class EmploymentStatus(str, Enum):
    """Current standing of an employee within the organization.
 
    Distinct from `SoftDeleteMixin.is_deleted`: a `TERMINATED` employee
    is still a real historical record and remains queryable; a
    soft-deleted employee is a record that was created in error or is
    being fully retired from the system.
    """
 
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
 
 
class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERN = "intern"
 