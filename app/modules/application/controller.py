from uuid import UUID

from fastapi import BackgroundTasks, UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.modules.application.schemas import (
    ApplicationDocumentResponse,
    ApplicationResponse,
    ApplicationCreateRequest,
    ApplicationSubmitRequest,
    ApplicationActionRequest,
    ApplicationAISummaryEnvelope,
)
from app.modules.application.service import ApplicationService
from app.modules.application.ai_engine import DocumentAIEngine
from app.modules.application.ai_service import DocumentAIService


class ApplicationController:
    def __init__(self) -> None:
        self.service = ApplicationService()
        self.ai_engine = DocumentAIEngine()
        self.ai_service = DocumentAIService(self.ai_engine)

    async def _run_ai_analysis_and_persist(self, application_id: UUID, candidate_user_id: int) -> None:
        from sqlalchemy import select, update
        from app.db.session import AsyncSessionLocal
        from app.models.application import Application
        from app.models.application_document import ApplicationDocument
        from app.models.candidate import Candidate
        import json
        import logging
        logger = logging.getLogger(__name__)

        async with AsyncSessionLocal() as db:
            try:
                logger.info(f"Starting AI Scrutiny for application {application_id}")
                app = (await db.execute(select(Application).where(Application.id == application_id))).scalars().first()
                if not app:
                    logger.warning(f"Application {application_id} not found for AI Scrutiny")
                    return
                docs_list = (
                    await db.execute(
                        select(ApplicationDocument)
                        .where(ApplicationDocument.application_id == application_id)
                        .order_by(ApplicationDocument.uploaded_at.asc())
                    )
                ).scalars().all()
                if not docs_list:
                    logger.info(f"No documents found for application {application_id}")
                    return

                candidate_obj = (
                    await db.execute(
                        select(Candidate)
                        .where(Candidate.user_id == candidate_user_id)
                        .options(selectinload(Candidate.qualifications), selectinload(Candidate.experiences))
                    )
                ).scalars().first()
                if not candidate_obj:
                    logger.warning(f"Candidate not found for user {candidate_user_id}")
                    return

                docs_metadata = [{"type": d.document_type, "path": d.file_path} for d in docs_list]
                candidate_profile = self._candidate_profile(candidate_obj)
                
                logger.info(f"Calling AI Service for {len(docs_metadata)} documents...")
                ai_result = await self.ai_service.process(docs_metadata, candidate_profile)
                logger.info(f"AI Service response received for app {application_id}. Status: {ai_result.get('status')}")

                ai_confidence = ai_result.get("confidence_score", 0.0)
                try:
                    ai_confidence_pct = int(float(ai_confidence) * 100)
                except (TypeError, ValueError):
                    ai_confidence_pct = 0
                ai_confidence_pct = max(0, min(100, ai_confidence_pct))

                await db.execute(
                    update(Application)
                    .where(Application.id == application_id)
                    .values(
                        ai_status=ai_result.get("status", "REQUIRES_REVIEW"),
                        ai_scrutiny_data=json.dumps(ai_result),
                        ai_confidence_score=ai_confidence_pct,
                    )
                )

                # Update individual document statuses
                doc_analysis = ai_result.get("document_analysis", [])
                for doc_res in doc_analysis:
                    dtype = doc_res.get("document_type")
                    issues = doc_res.get("issues", [])
                    
                    # Basic heuristic for status
                    v_status = "VALID" if not issues else "INVALID"
                    v_msg = "; ".join(issues) if issues else None
                    
                    for d in docs_list:
                        if d.document_type == dtype:
                            d.validation_status = v_status
                            d.validation_message = v_msg
                            db.add(d) # Mark for update

                await db.commit()
                logger.info(f"Successfully persisted AI Scrutiny results for application {application_id}")
            except Exception as e:
                logger.error(f"AI Scrutiny Background Task failed for app {application_id}: {str(e)}")
                # Optionally update app status to ERROR
                try:
                    await db.execute(
                        update(Application)
                        .where(Application.id == application_id)
                        .values(ai_status="REQUIRES_REVIEW")
                    )
                    await db.commit()
                except:
                    pass

    async def create_application(self, db: AsyncSession, current_user: User, req: ApplicationCreateRequest):
        data = await self.service.create_application(db, current_user, req)
        payload = ApplicationResponse.model_validate(data, from_attributes=True).model_dump()
        return {"status": "success", "data": payload}

    async def upload_documents_bulk(
        self,
        db: AsyncSession,
        current_user: User,
        application_id: UUID,
        files: list[UploadFile],
        background_tasks: BackgroundTasks,
        document_type: str | None = None,
    ):
        # 1. Bulk upload
        docs = await self.service.upload_documents_bulk(
            db,
            current_user,
            application_id,
            files,
            background_tasks,
            document_type=document_type,
        )
        
        # 2. Trigger AI scrutiny
        background_tasks.add_task(self._run_ai_analysis_and_persist, application_id, current_user.id)
        
        from app.modules.application.schemas import ApplicationDocumentResponse
        return {
            "status": "success", 
            "data": [ApplicationDocumentResponse.model_validate(d, from_attributes=True).model_dump() for d in docs],
            "ai_analysis": {"status": "QUEUED", "message": "AI scrutiny queued for background processing"},
        }

    async def analyze_application_ai(self, db: AsyncSession, application_id: UUID, current_user: User):
        from sqlalchemy import select, update
        from app.models.application import Application
        from app.models.candidate import Candidate
        import json

        app = (await db.execute(select(Application).where(Application.id == application_id))).scalars().first()
        if not app:
            raise HTTPException(status_code=404, detail={"code": "APPLICATION_NOT_FOUND", "message": "Application not found"})

        await self.service.assert_application_view_access(db, current_user, app)

        docs_list = await self.service.list_documents(db, current_user, application_id)
        candidate = (
            await db.execute(
                select(Candidate)
                .where(Candidate.id == app.candidate_id)
                .options(selectinload(Candidate.qualifications), selectinload(Candidate.experiences))
            )
        ).scalars().first()
        if not candidate:
            raise HTTPException(status_code=404, detail={"code": "CANDIDATE_NOT_FOUND", "message": "Candidate not found for application"})

        docs_metadata = [{"type": d.document_type, "path": d.file_path} for d in docs_list]
        candidate_profile = self._candidate_profile(candidate)
        ai_result = await self.ai_service.process(docs_metadata, candidate_profile)

        ai_confidence = ai_result.get("confidence_score", 0.0)
        try:
            ai_confidence_pct = int(float(ai_confidence) * 100)
        except (TypeError, ValueError):
            ai_confidence_pct = 0
        ai_confidence_pct = max(0, min(100, ai_confidence_pct))

        await db.execute(
            update(Application)
            .where(Application.id == application_id)
            .values(
                ai_status=ai_result.get("status", "REQUIRES_REVIEW"),
                ai_scrutiny_data=json.dumps(ai_result),
                ai_confidence_score=ai_confidence_pct
            )
        )
        await db.commit()

        return {
            "status": "success",
            "data": {
                "classification": ai_result.get("status", "REQUIRES_REVIEW"),
                "scrutiny_summary": ai_result.get("scrutiny_summary", ""),
                "missing_documents": ai_result.get("missing_documents", []),
                "mismatches": ai_result.get("mismatches", []),
                "confidence_score": ai_result.get("confidence_score", 0.0),
            },
        }

    async def get_application_ai_summary(self, db: AsyncSession, application_id: UUID, current_user: User):
        from sqlalchemy import select
        from app.models.application import Application
        import json
        
        stmt = select(Application).where(Application.id == application_id)
        app = (await db.execute(stmt)).scalars().first()
        
        if not app:
            raise HTTPException(status_code=404, detail={"code": "APPLICATION_NOT_FOUND", "message": "Application not found"})

        await self.service.assert_application_view_access(db, current_user, app)
            
        ai_data = json.loads(app.ai_scrutiny_data) if app.ai_scrutiny_data else {}
        
        return {
            "status": "success",
            "data": {
                "id": app.id,
                "ai_status": app.ai_status,
                "scrutiny_summary": ai_data.get("scrutiny_summary", "No analysis available"),
                "issues": [issue for doc in ai_data.get("document_analysis", []) for issue in doc.get("issues", [])],
                "confidence_score": app.ai_confidence_score / 100.0 if app.ai_confidence_score else 0.0
            }
        }

    async def list_documents(self, db: AsyncSession, current_user: User, application_id: UUID):
        data = await self.service.list_documents(db, current_user, application_id)
        payload = [ApplicationDocumentResponse.model_validate(item, from_attributes=True).model_dump() for item in data]
        return {"status": "success", "data": payload}

    async def submit_application(
        self,
        db: AsyncSession,
        current_user: User,
        application_id: UUID,
        req: ApplicationSubmitRequest,
    ):
        data = await self.service.submit_application(db, current_user, application_id, req)
        return {"status": "success", "data": data}

    async def process_application_action(
        self,
        db: AsyncSession,
        current_user: User,
        application_id: UUID,
        req: ApplicationActionRequest,
    ):
        app = await self.service.process_application_action(db, current_user, application_id, req)
        return {"status": "success", "data": ApplicationResponse.model_validate(app, from_attributes=True).model_dump()}

    async def withdraw_application(self, db: AsyncSession, current_user: User, application_id: UUID):
        data = await self.service.withdraw_application(db, current_user, application_id)
        payload = ApplicationResponse.model_validate(data, from_attributes=True).model_dump()
        return {"status": "success", "data": payload}

    async def list_my_applications(self, db: AsyncSession, current_user: User, skip: int = 0, limit: int = 10):
        data, total = await self.service.list_my_applications(db, current_user, skip, limit)
        import math
        return {
            "status": "success",
            "data": data,
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0
        }

    async def list_applications(
        self,
        db: AsyncSession,
        current_user: User,
        advertisement_id: UUID | None,
        status: str | None,
        course_id: int | None,
        academic_year: str | None,
        skip: int = 0,
        limit: int = 10,
    ):
        data, total = await self.service.list_applications(
            db,
            current_user,
            advertisement_id=advertisement_id,
            status=status,
            course_id=course_id,
            academic_year=academic_year,
            skip=skip,
            limit=limit,
        )
        import math
        return {
            "status": "success",
            "data": data,
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0
        }
    @staticmethod
    def _candidate_profile(candidate_obj) -> dict:
        quals = []
        exps = []
        for q in getattr(candidate_obj, "qualifications", []) or []:
            vals = [getattr(q, "degree", None), getattr(q, "specialization", None), getattr(q, "university", None)]
            quals.append(", ".join([v for v in vals if v]))
        for e in getattr(candidate_obj, "experiences", []) or []:
            vals = [getattr(e, "designation", None), getattr(e, "institution_name", None)]
            exps.append(", ".join([v for v in vals if v]))
        return {
            "name": candidate_obj.full_name,
            "qualifications": "; ".join(quals) if quals else "Not Specified",
            "experience": "; ".join(exps) if exps else "Not Specified",
        }
