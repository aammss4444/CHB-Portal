import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, and_
import sys
import os

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.db.session import engine, Base
from app.models.appointment_template import AppointmentTemplate

EN_TEMPLATE = """
<div style="font-family: Arial, sans-serif; line-height: 1.6; padding: 40px; color: #1e293b;">
    <div style="text-align: center; margin-bottom: 40px;">
        <h1 style="color: #0f172a; margin-bottom: 8px;">APPOINTMENT LETTER</h1>
        <p style="color: #64748b; font-size: 14px;">Clock Hour Basis (CHB) Recruitment</p>
    </div>
    
    <div style="display: flex; justify-content: space-between; margin-bottom: 30px;">
        <div>
            <p><strong>Ref:</strong> {{ appointment_number }}</p>
        </div>
        <div style="text-align: right;">
            <p><strong>Date:</strong> {{ issue_date }}</p>
        </div>
    </div>

    <p>To,<br/><strong>{{ candidate_name }}</strong></p>
    <br/>
    <p><strong>Subject: Offer of Appointment for the post of {{ designation }} (CHB)</strong></p>
    <br/>
    <p>Dear {{ candidate_name }},</p>
    <p>With reference to your application and performance in the selection process, we are pleased to offer you an appointment as <strong>{{ designation }}</strong> in the Department of <strong>{{ course_name }}</strong> at <strong>{{ institution_name }}</strong> for the Academic Year {{ academic_year }}.</p>
    
    <p>The terms and conditions of your appointment are as follows:</p>
    <ol>
        <li><strong>Nature of Appointment:</strong> This appointment is purely on a temporary Clock Hour Basis (CHB) and does not confer any right for permanent absorption.</li>
        <li><strong>Remuneration:</strong> You will be paid a honorarium of <strong>{{ salary_per_lecture }}</strong> per lecture, subject to a maximum number of lectures as per DTE and Government norms.</li>
        <li><strong>Joining:</strong> You are required to report for duty on or before <strong>{{ joining_date }}</strong>.</li>
        <li><strong>Acceptance:</strong> Please confirm your acceptance of this offer by <strong>{{ acceptance_deadline }}</strong>.</li>
    </ol>
    
    <p>We look forward to your contribution to our institution.</p>
    <br/><br/>
    <div style="margin-top: 40px;">
        <p>Sincerely,</p>
        <br/>
        <p><strong>{{ principal_name }}</strong><br/>Principal<br/>{{ institution_name }}</p>
    </div>
</div>
"""

MR_TEMPLATE = """
<div style="font-family: 'Arial Unicode MS', sans-serif; line-height: 1.6; padding: 40px; color: #1e293b;">
    <div style="text-align: center; margin-bottom: 40px;">
        <h1 style="color: #0f172a; margin-bottom: 8px;">नियुक्ती पत्र</h1>
        <p style="color: #64748b; font-size: 14px;">तासिका तत्त्व (CHB) भरती</p>
    </div>
    
    <div style="display: flex; justify-content: space-between; margin-bottom: 30px;">
        <div>
            <p><strong>संदर्भ:</strong> {{ appointment_number }}</p>
        </div>
        <div style="text-align: right;">
            <p><strong>दिनांक:</strong> {{ issue_date }}</p>
        </div>
    </div>

    <p>प्रति,<br/><strong>{{ candidate_name }}</strong></p>
    <br/>
    <p><strong>विषय: {{ designation }} (तासिका तत्त्व) पदावर नियुक्तीबाबत.</strong></p>
    <br/>
    <p>प्रिय {{ candidate_name }},</p>
    <p>तुमचा अर्ज आणि निवड प्रक्रियेतील तुमच्या कामगिरीच्या संदर्भात, आम्हाला तुम्हाला <strong>{{ institution_name }}</strong> येथे शैक्षणिक वर्ष {{ academic_year }} साठी <strong>{{ course_name }}</strong> विभागात <strong>{{ designation }}</strong> म्हणून नियुक्ती ऑफर करताना आनंद होत आहे.</p>
    
    <p>तुमच्या नियुक्तीच्या अटी व शर्ती खालीलप्रमाणे आहेत:</p>
    <ol>
        <li><strong>नियुक्तीचे स्वरूप:</strong> ही नियुक्ती पूर्णपणे तात्पुरत्या तासिका तत्त्वावर (CHB) आहे आणि कायमस्वरूपी समावेशासाठी कोणताही अधिकार प्रदान करत नाही.</li>
        <li><strong>मानधन:</strong> तुम्हाला DTE आणि सरकारी नियमांनुसार दर व्याख्यानासाठी <strong>{{ salary_per_lecture }}</strong> मानधन दिले जाईल.</li>
        <li><strong>रुजू होणे:</strong> तुम्हाला <strong>{{ joining_date }}</strong> रोजी किंवा त्यापूर्वी कर्तव्यावर हजर राहणे आवश्यक आहे.</li>
        <li><strong>स्वीकृती:</strong> कृपया या ऑफरची तुमची स्वीकृती <strong>{{ acceptance_deadline }}</strong> पर्यंत निश्चित करा.</li>
    </ol>
    
    <p>आम्ही आमच्या संस्थेतील तुमच्या योगदानासाठी उत्सुक आहोत.</p>
    <br/><br/>
    <div style="margin-top: 40px;">
        <p>आपला नम्र,</p>
        <br/>
        <p><strong>{{ principal_name }}</strong><br/>प्राचार्य<br/>{{ institution_name }}</p>
    </div>
</div>
"""

async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Check if templates exist
        for lang, body, name in [("EN", EN_TEMPLATE, "Standard English Template"), ("MR", MR_TEMPLATE, "Standard Marathi Template")]:
            stmt = select(AppointmentTemplate).where(and_(AppointmentTemplate.language == lang, AppointmentTemplate.is_active == True))
            result = await session.execute(stmt)
            if not result.scalars().first():
                print(f"Seeding {lang} template...")
                session.add(AppointmentTemplate(
                    name=name,
                    template_body=body,
                    language=lang,
                    is_active=True
                ))
        await session.commit()
    print("Seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed())
