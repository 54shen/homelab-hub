# ============================================================
# Shared Center — Token 认证
# ============================================================
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from models import Token as TokenModel

security = HTTPBearer(auto_error=False)


def auth_write(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> TokenModel:
    """写操作强制认证。
    无 Token → 401，Token 无效 → 401，权限不足 → 403
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="需要认证 Token，请在 Header 中添加: Authorization: Bearer <token>")

    token_str = credentials.credentials
    token_record = db.query(TokenModel).filter(TokenModel.token == token_str).first()
    if not token_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或不存在")

    if token_record.permission not in ("write", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"权限不足（当前: {token_record.permission}，需要: write 或 admin）")

    return token_record
