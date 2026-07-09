# models.py
import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Recording(Base):
    __tablename__ = "recordings"

    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    title = Column(String, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="uploaded")
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    transcripts = relationship(
        "Transcript", back_populates="recording", cascade="all, delete-orphan"
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True)
    recording_id = Column(Integer, ForeignKey("recordings.id"), nullable=False)
    text = Column(Text, nullable=False)
    utterances = Column(Text, nullable=True)  # JSON-encoded list of {speaker, text}
    assemblyai_job_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    recording = relationship("Recording", back_populates="transcripts")
    generations = relationship(
        "Generation", back_populates="transcript", cascade="all, delete-orphan"
    )


class Generation(Base):
    __tablename__ = "generations"

    id = Column(Integer, primary_key=True)
    transcript_id = Column(Integer, ForeignKey("transcripts.id"), nullable=False)
    mode = Column(String, nullable=False)
    output_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    transcript = relationship("Transcript", back_populates="generations")
