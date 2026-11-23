"""Dados iniciais (funil padrão, origens, motivos, admin) e, opcionalmente, dados de exemplo.

Uso:
    python -m app.seed            # só o essencial (idempotente)
    python -m app.seed --exemplo  # + usuários e leads fictícios para demonstração
"""
import random
import sys
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal, agora
from .models import (
    Estagio,
    Etiqueta,
    HistoricoEstagio,
    Interacao,
    Lead,
    ModeloEmail,
    MotivoPerda,
    Origem,
    Tarefa,
    Usuario,
)
from .seguranca import hash_senha

ESTAGIOS = [("Novo", "aberto", "#2563eb"), ("Contatado", "aberto", "#0891b2"), ("Qualificado", "aberto", "#7c3aed"),
            ("Proposta enviada", "aberto", "#c2410c"), ("Negociação", "aberto", "#b45309"),
            ("Ganho", "ganho", "#15803d"), ("Perdido", "perdido", "#b91c1c")]
ORIGENS = ["Formulário do site", "Indicação", "Redes sociais", "Evento", "Ligação", "E-mail"]
MOTIVOS = ["Preço", "Escolheu concorrente", "Sem orçamento", "Sem resposta", "Fora do perfil", "Adiou a decisão"]
ETIQUETAS = [("Prioridade", "#b91c1c"), ("Grande conta", "#7c3aed"), ("Retorno", "#0e7490")]
MODELOS = [
    ("Primeiro contato", "{{primeiro_nome}}, obrigado pelo interesse na Tenti",
     "Olá, {{primeiro_nome}}!\n\nObrigado pelo interesse em {{interesse}}. Podemos conversar 15 minutos esta semana "
     "para entender a necessidade da {{empresa}}?\n\nAtenciosamente,\n{{vendedor}}\nComercial Tenti"),
    ("Follow-up de proposta", "Proposta Tenti — próximos passos",
     "Olá, {{primeiro_nome}}!\n\nConseguiu avaliar a proposta que enviamos? Fico à disposição para tirar dúvidas."
     "\n\nAtenciosamente,\n{{vendedor}}"),
]


def essencial(db: Session) -> None:
    if not db.scalar(select(Estagio.id).limit(1)):
        for i, (nome, tipo, cor) in enumerate(ESTAGIOS, start=1):
            db.add(Estagio(nome=nome, ordem=i, tipo=tipo, cor=cor))
    for nome in ORIGENS:
        if not db.scalar(select(Origem.id).where(Origem.nome == nome)):
            db.add(Origem(nome=nome))
    for nome in MOTIVOS:
        if not db.scalar(select(MotivoPerda.id).where(MotivoPerda.nome == nome)):
            db.add(MotivoPerda(nome=nome))
    for nome, cor in ETIQUETAS:
        if not db.scalar(select(Etiqueta.id).where(Etiqueta.nome == nome)):
            db.add(Etiqueta(nome=nome, cor=cor))
    if not db.scalar(select(ModeloEmail.id).limit(1)):
        for nome, assunto, corpo in MODELOS:
            db.add(ModeloEmail(nome=nome, assunto=assunto, corpo=corpo))
    s = get_settings()
    if not db.scalar(select(Usuario.id).where(Usuario.perfil == "admin")):
        db.add(Usuario(nome="Administrador", email=s.seed_admin_email, senha_hash=hash_senha(s.seed_admin_senha),
                       perfil="admin"))
    db.commit()


NOMES = ["Ana Lima", "Bruno Costa", "Carla Mendes", "Daniel Rocha", "Eduarda Alves", "Felipe Nunes", "Gabriela Dias",
         "Henrique Moraes", "Isabela Freitas", "João Pedro Santos", "Karina Lopes", "Lucas Barbosa", "Mariana Teixeira",
         "Nicolas Pereira", "Olívia Cardoso", "Paulo Ribeiro", "Queila Martins", "Rafael Gomes", "Sofia Araújo",
         "Thiago Carvalho", "Ursula Pinto", "Vinícius Correia", "Yasmin Fernandes", "Wagner Duarte"]
EMPRESAS = ["Alfa Logística", "Beta Engenharia", "Construtora Horizonte", "Delta Alimentos", "Escola Saber",
            "Farmácia Vida", "Grupo Nativa", "Hotel Mirante", "Indústria Prisma", "Jardim & Cia"]
CIDADES = [("São Paulo", "SP"), ("Campinas", "SP"), ("Rio de Janeiro", "RJ"), ("Belo Horizonte", "MG"),
           ("Curitiba", "PR"), ("Porto Alegre", "RS"), ("Salvador", "BA"), ("Recife", "PE")]
INTERESSES = ["Consultoria", "Treinamento", "Implantação", "Suporte mensal"]


def exemplo(db: Session) -> None:
    if db.scalar(select(Lead.id).limit(1)):
        print("Já existem leads; dados de exemplo não foram gerados.")
        return
    rnd = random.Random(42)
    senha = hash_senha("Senha@123")
    equipe = []
    for nome, email, perfil in [("Gabriel Gestor", "gestor@tenti.com.br", "gestor"),
                                ("Valéria Vendas", "valeria@tenti.com.br", "vendedor"),
                                ("Victor Vendas", "victor@tenti.com.br", "vendedor"),
                                ("Vanessa Vendas", "vanessa@tenti.com.br", "vendedor"),
                                ("Lúcia Leitura", "leitura@tenti.com.br", "leitura")]:
        u = db.scalar(select(Usuario).where(Usuario.email == email))
        if not u:
            u = Usuario(nome=nome, email=email, perfil=perfil, senha_hash=senha)
            db.add(u)
        equipe.append(u)
    db.flush()
    vendedores = [u for u in equipe if u.perfil == "vendedor"]
    estagios = list(db.scalars(select(Estagio).order_by(Estagio.ordem)))
    abertos = [e for e in estagios if e.tipo == "aberto"]
    ganho = next(e for e in estagios if e.tipo == "ganho")
    perdido = next(e for e in estagios if e.tipo == "perdido")
    origens = list(db.scalars(select(Origem)))
    motivos = list(db.scalars(select(MotivoPerda)))
    etiquetas = list(db.scalars(select(Etiqueta)))
    agora_ = agora()
    for i in range(60):
        nome = NOMES[i % len(NOMES)] + ("" if i < len(NOMES) else f" {i}")
        cidade, uf = rnd.choice(CIDADES)
        criado = agora_ - timedelta(days=rnd.randint(0, 75), hours=rnd.randint(0, 23))
        resp = rnd.choice(vendedores)
        lead = Lead(nome=nome, email=f"{nome.split()[0].lower()}.{i}@exemplo.com.br",
                    telefone=f"+55119{rnd.randint(10000000, 99999999)}", empresa=rnd.choice(EMPRESAS),
                    cargo=rnd.choice(["Diretor", "Gerente", "Analista", "Sócio"]), cidade=cidade, uf=uf,
                    interesse=rnd.choice(INTERESSES), valor_estimado=Decimal(rnd.randrange(3000, 80000, 500)),
                    origem_id=rnd.choice(origens).id, estagio_id=abertos[0].id, responsavel_id=resp.id,
                    criado_em=criado, estagio_desde=criado, base_legal="legitimo_interesse")
        if rnd.random() < 0.3:
            lead.etiquetas = [rnd.choice(etiquetas)]
        db.add(lead)
        db.flush()
        db.add(HistoricoEstagio(lead_id=lead.id, para_estagio_id=abertos[0].id, data_hora=criado))
        db.add(Interacao(lead_id=lead.id, tipo="sistema", data_hora=criado, resumo="Lead criado (dados de exemplo).",
                         dados={"evento": "criado"}))
        passos = rnd.choices(range(0, 7), weights=[18, 18, 16, 14, 12, 12, 10])[0]
        momento = criado
        atual = abertos[0]
        for p in range(1, passos + 1):
            momento = momento + timedelta(days=rnd.randint(1, 6), hours=rnd.randint(1, 8))
            if momento >= agora_:
                break
            if p == 1:
                lead.primeiro_contato_em = momento - timedelta(hours=rnd.randint(1, 20))
            destino = abertos[p] if p < len(abertos) else (ganho if rnd.random() < 0.55 else perdido)
            if p >= 3 and rnd.random() < 0.15:
                destino = perdido
            db.add(Interacao(lead_id=lead.id, usuario_id=resp.id, tipo=rnd.choice(["ligacao", "email", "reuniao"]),
                             data_hora=momento - timedelta(hours=1), resumo=f"Contato com {nome.split()[0]} sobre "
                             f"{lead.interesse.lower()}.", resultado=rnd.choice(["Interessado", "Pediu retorno",
                                                                                  "Enviou informações"])))
            db.add(HistoricoEstagio(lead_id=lead.id, de_estagio_id=atual.id, para_estagio_id=destino.id,
                                    usuario_id=resp.id, data_hora=momento))
            db.add(Interacao(lead_id=lead.id, usuario_id=resp.id, tipo="sistema", data_hora=momento,
                             resumo=f"Estágio alterado de “{atual.nome}” para “{destino.nome}”.",
                             dados={"evento": "estagio"}))
            lead.ultimo_contato_em = momento - timedelta(hours=1)
            atual = destino
            lead.estagio_desde = momento
            if destino.tipo == "ganho":
                lead.valor_fechado = (lead.valor_estimado * Decimal("0.9")).quantize(Decimal("1"))
                lead.fechado_em = momento
                break
            if destino.tipo == "perdido":
                lead.motivo_perda_id = rnd.choice(motivos).id
                lead.fechado_em = momento
                break
        lead.estagio_id = atual.id
        if atual.tipo == "aberto" and rnd.random() < 0.65:
            venc = agora_ + timedelta(days=rnd.randint(-4, 8), hours=rnd.randint(0, 6))
            db.add(Tarefa(lead_id=lead.id, responsavel_id=resp.id, vencimento=venc,
                          titulo=rnd.choice(["Ligar para retomar contato", "Enviar proposta", "Agendar reunião",
                                             "Confirmar recebimento da proposta"])))
    db.commit()
    print("Dados de exemplo criados. Usuários: gestor@, valeria@, victor@, vanessa@, leitura@tenti.com.br "
          "(senha: Senha@123).")


def main() -> None:
    db = SessionLocal()
    try:
        essencial(db)
        if "--exemplo" in sys.argv:
            exemplo(db)
        print("Seed concluído.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
