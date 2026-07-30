# ============================================================
# Shared Center — Token 认证
# ============================================================
from typing import Optional, Union
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from models import Token as TokenModel, Session as SessionModel

security = HTTPBearer(auto_error=False)


def auth_write(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Union[TokenModel, SessionModel]:
    """写操作强制认证。同时支持 API Token (sk-xxx) 和 Web 会话 Token (ws-xxx)。
    无 Token → 401，Token 无效 → 401，权限不足 → 403
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="需要认证 Token，请在 Header 中添加: Authorization: Bearer <token>")

    token_str = credentials.credentials

    # 先查 API Token 表，再查 Web 会话表（与中间件逻辑一致）
    token_record = db.query(TokenModel).filter(TokenModel.token == token_str).first()
    session_record = db.query(SessionModel).filter(SessionModel.session_token == token_str).first() if not token_record else None

    if not token_record and not session_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或不存在")

    permission = token_record.permission if token_record else session_record.permission
    if permission not in ("write", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"权限不足（当前: {permission}，需要: write 或 admin）")

    return token_record or session_record
