from fastapi import HTTPException, status, Depends
from app.models.user import User, RoleEnum
from app.core.security import get_current_user

async def verify_institution_access(institution_id: int, current_user: User = Depends(get_current_user)):
    """
    Dependency to ensure a Principal can only access their own institution.
    Admins can access everything.
    """
    if current_user.role == RoleEnum.ADMIN:
        return True
        
    # Assuming the User model has an institution_id field. 
    # If not, we might need to add it to the User model.
    # For now, I'll check if it exists on the user object.
    
    user_inst_id = getattr(current_user, "institution_id", None)
    
    if current_user.role == RoleEnum.PRINCIPAL:
        if user_inst_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not assigned to any institution. Please contact the administrator."
            )
        
        # Ensure comparison is robust (e.g. if one is string from query and one is int from db)
        if int(user_inst_id) != int(institution_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: You are mapped to Institution ID {user_inst_id}, but requested data for ID {institution_id}."
            )
    
    return True
