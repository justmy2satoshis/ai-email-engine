"""Proposal management API endpoints."""

from fastapi import APIRouter, Query
from typing import Optional

from app.services.proposal_engine import proposal_engine

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


@router.post("/generate")
async def generate_proposals():
    """Generate all cleanup proposals (unsubscribe, archive, extraction)."""
    results = await proposal_engine.generate_all_proposals()
    return {
        "generated": len(results),
        "proposals": results,
    }


@router.get("/")
async def list_proposals(status: Optional[str] = Query(None, description="Filter: pending, approved, rejected, executed")):
    """List all proposals with optional status filter."""
    return await proposal_engine.list_proposals(status=status)


@router.post("/{proposal_id}/approve")
async def approve_proposal(proposal_id: int):
    """Approve a cleanup proposal."""
    return await proposal_engine.approve_proposal(proposal_id)


@router.post("/{proposal_id}/reject")
async def reject_proposal(proposal_id: int):
    """Reject a cleanup proposal."""
    return await proposal_engine.reject_proposal(proposal_id)
