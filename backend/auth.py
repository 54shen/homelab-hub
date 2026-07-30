# ============================================================
# Shared Center — JWT 认证
# ============================================================
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, AUTH_REQUIRED
from database import get_db
from models import Token as TokenModel

security = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> TokenModel:
    """验证请求 Token 是否有效，返回 Token 记录"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证 Token")

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        token_value = payload.get("sub", "")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")

    token_record = db.query(TokenModel).filter(TokenModel.token == token_value).first()
    if not token_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 不存在")

    return token_record


def require_permission(permission: str):
    """权限检查依赖"""

    def checker(token: TokenModel = Depends(get_current_token)):
        if token.permission == "admin":
            return token
        if permission == "read" and token.permission in ("read", "write", "admin"):
            return token
        if permission == "write" and token.permission in ("write", "admin"):
            return token
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")

    return checker


def verify_token(token_str: str, db: Session) -> Optional[TokenModel]:
    """验证 Token 字符串，用于设备接入"""
    return db.query(TokenModel).filter(TokenModel.token == token_str).first()


def auth_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[TokenModel]:
    """可选的认证检查。
    - AUTH_REQUIRED=false: 直接放行，返回 None
    - AUTH_REQUIRED=true: 无 Token → 401，有 Token → 验证通过返回 TokenModel
    """
    if not AUTH_REQUIRED:
        return None

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证 Token，请在 Header 中添加 Authorization: Bearer <token>")

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        token_value = payload.get("sub", "")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")

    token_record = db.query(TokenModel).filter(TokenModel.token == token_value).first()
    if not token_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 不存在或已被删除")

    return token_record  # 当前 Token 记录
