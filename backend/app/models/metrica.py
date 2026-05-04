from datetime import date
from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class MetricaDiaria(Base):
    __tablename__ = "metricas_diarias"

    data: Mapped[date] = mapped_column(Date, primary_key=True)
    anuncios_coletados: Mapped[int] = mapped_column(Integer, default=0)
    anuncios_novos: Mapped[int] = mapped_column(Integer, default=0)
    msgs_enviadas: Mapped[int] = mapped_column(Integer, default=0)
    msgs_entregues: Mapped[int] = mapped_column(Integer, default=0)
    respostas_recebidas: Mapped[int] = mapped_column(Integer, default=0)
    leads_qualificados: Mapped[int] = mapped_column(Integer, default=0)
    leads_escalados: Mapped[int] = mapped_column(Integer, default=0)
    opt_outs_dia: Mapped[int] = mapped_column(Integer, default=0)
