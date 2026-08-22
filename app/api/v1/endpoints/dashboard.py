from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ....core.database import get_db                 # ✅ 4 dots
from ....core.security import get_current_user       # ✅ 4 dots + security
from ....models.user import User                     # ✅ 4 dots
from ....models.document import Document, DocumentStatus

router = APIRouter()

@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total = db.query(Document).filter(Document.owner_id == current_user.id).count()
    analyzed = db.query(Document).filter(
        Document.owner_id == current_user.id,
        Document.status == DocumentStatus.COMPLETED
    ).count()
    recent_docs = db.query(Document).filter(
        Document.owner_id == current_user.id,
        Document.status == DocumentStatus.COMPLETED
    ).order_by(Document.created_at.desc()).limit(5).all()
    
    return {
        "total_documents": total,
        "documents_analyzed": analyzed,
        "average_risk_score": None,
        "ai_queries": 0,
        "recent_documents": recent_docs,
    }