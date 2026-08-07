from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.orchestrator import get_conversation_owned, process_message
from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.entities import ChatConversation, ChatMessage, FinancialChangeProposal, ProposalStatus, User, UserAIMemory
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    MemoryCreate,
    MemoryResponse,
    MessageCreate,
    ProposalActionResponse,
    ProposalResponse,
)
from app.services.proposals import (
    confirm_proposal,
    get_proposal_owned,
    proposal_response,
    reject_proposal,
    reverse_proposal,
)

router = APIRouter(prefix="/chat", tags=["AI financial assistant"])


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
def create_conversation(payload: ConversationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = ChatConversation(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(ChatConversation).where(ChatConversation.user_id == user.id).order_by(ChatConversation.updated_at.desc())).all()


@router.get("/conversations/{conversation_id}", response_model=dict)
def get_conversation(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = get_conversation_owned(db, user.id, conversation_id)
    messages = db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conversation.id, ChatMessage.user_id == user.id).order_by(ChatMessage.created_at)).all()
    return {
        "conversation": ConversationResponse.model_validate(conversation).model_dump(mode="json"),
        "messages": [
            {"id": item.id, "role": item.role, "content": item.content, "created_at": item.created_at.isoformat()}
            for item in messages
        ],
    }


@router.put("/conversations/{conversation_id}", response_model=ConversationResponse)
def update_conversation(conversation_id: str, payload: ConversationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = get_conversation_owned(db, user.id, conversation_id)
    item.title = payload.title
    item.mode = payload.mode
    db.commit()
    db.refresh(item)
    return item


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = get_conversation_owned(db, user.id, conversation_id)
    db.delete(item)
    db.commit()


@router.post("/conversations/{conversation_id}/messages", response_model=ChatResponse)
def send_message(conversation_id: str, payload: MessageCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = get_conversation_owned(db, user.id, conversation_id)
    return process_message(
        db,
        user=user,
        message=payload.message,
        conversation_id=conversation.id,
        mode=payload.mode or conversation.mode,
    )


@router.post("/messages", response_model=ChatResponse)
def compatibility_chat(payload: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return process_message(db, user=user, message=payload.message)


@router.get("/proposals", response_model=list[ProposalResponse])
def list_proposals(
    proposal_status: ProposalStatus | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(FinancialChangeProposal).where(FinancialChangeProposal.user_id == user.id)
    if proposal_status:
        query = query.where(FinancialChangeProposal.status == proposal_status)
    items = db.scalars(query.order_by(FinancialChangeProposal.created_at.desc())).all()
    return [proposal_response(item) for item in items]


@router.get("/proposals/{proposal_id}", response_model=ProposalResponse)
def get_proposal(proposal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return proposal_response(get_proposal_owned(db, user.id, proposal_id))


@router.post("/proposals/{proposal_id}/confirm", response_model=ProposalActionResponse)
def confirm_change(proposal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    proposal = get_proposal_owned(db, user.id, proposal_id)
    plan = confirm_proposal(db, user=user, proposal=proposal)
    db.refresh(proposal)
    return ProposalActionResponse(proposal=proposal_response(proposal), plan=plan)


@router.post("/proposals/{proposal_id}/reject", response_model=ProposalResponse)
def reject_change(proposal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    proposal = get_proposal_owned(db, user.id, proposal_id)
    reject_proposal(db, user=user, proposal=proposal)
    db.refresh(proposal)
    return proposal_response(proposal)


@router.post("/proposals/{proposal_id}/recalculate", response_model=ChatResponse)
def recalculate_change(proposal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    proposal = get_proposal_owned(db, user.id, proposal_id)
    if proposal.status == ProposalStatus.applied:
        raise HTTPException(status_code=409, detail="An applied proposal cannot be recalculated")
    proposal.status = ProposalStatus.expired
    db.flush()
    return process_message(
        db,
        user=user,
        message=proposal.original_request,
        conversation_id=proposal.conversation_id,
        mode="action",
    )


@router.post("/proposals/{proposal_id}/reverse", response_model=ProposalActionResponse)
def reverse_change(proposal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    proposal = get_proposal_owned(db, user.id, proposal_id)
    plan = reverse_proposal(db, user=user, proposal=proposal)
    db.refresh(proposal)
    return ProposalActionResponse(proposal=proposal_response(proposal), plan=plan)


@router.get("/suggested-questions", response_model=list[str])
def suggested_questions() -> list[str]:
    return [
        "How much can I safely spend this weekend?",
        "Can I afford a laptop costing SGD 1,500?",
        "Why am I over budget?",
        "Move SGD 100 from Online shopping to Smart Wishlist savings.",
        "Reduce Planned activities by SGD 50.",
        "Set my savings to 25%.",
        "I have an emergency repair costing SGD 800.",
    ]


@router.get("/memory", response_model=list[MemoryResponse])
def list_memory(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(UserAIMemory).where(UserAIMemory.user_id == user.id).order_by(UserAIMemory.updated_at.desc())).all()


@router.post("/memory", response_model=MemoryResponse, status_code=201)
def create_memory(payload: MemoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.profile and not user.profile.ai_memory_enabled:
        raise HTTPException(status_code=409, detail="Long-term AI memory is disabled")
    item = UserAIMemory(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/memory/{memory_id}", response_model=MemoryResponse)
def update_memory(memory_id: str, payload: MemoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(UserAIMemory).where(UserAIMemory.id == memory_id, UserAIMemory.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="AI memory not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/memory/{memory_id}", status_code=204)
def delete_memory(memory_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(UserAIMemory).where(UserAIMemory.id == memory_id, UserAIMemory.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="AI memory not found")
    db.delete(item)
    db.commit()


@router.delete("/memory", status_code=204)
def delete_all_memory(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(UserAIMemory).filter(UserAIMemory.user_id == user.id).delete(synchronize_session=False)
    db.commit()
