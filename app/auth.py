import datetime
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRY_HOURS
from app.database import get_db
from app.models import Provider

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Zwraca hash bcrypt dla podanego hasła."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Sprawdza, czy hasło zgadza się z hashem."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(provider_id: int) -> str:
    """Tworzy JWT token dostępu."""
    exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=JWT_EXPIRY_HOURS
    )
    payload = {
        "sub": str(provider_id),
        "exp": exp,
        "iat": datetime.datetime.now(datetime.timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[int]:
    """Dekoduje JWT token i zwraca provider_id lub None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        provider_id = payload.get("sub")
        if provider_id is None:
            return None
        return int(provider_id)
    except JWTError:
        return None


def get_current_provider(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Provider:
    """FastAPI dependency — zwraca aktualnie zalogowanego usługodawcę."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nie jesteś zalogowany",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provider_id = decode_access_token(credentials.credentials)
    if provider_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usługodawca nie istnieje",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return provider


def require_active_subscription(provider: Provider = Depends(get_current_provider)) -> Provider:
    """Sprawdza, czy usługodawca ma aktywną subskrypcję lub trial."""
    if provider.subscription_status == "canceled":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Subskrypcja została anulowana. Odnów subskrypcję, aby kontynuować.",
        )
    if provider.subscription_status in ("past_due", "incomplete"):
        if not provider.is_trial_active:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Wymagana jest aktywna subskrypcja. Przejdź do ustawień płatności.",
            )
    return provider
