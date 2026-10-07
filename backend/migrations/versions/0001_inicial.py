"""schema inicial do CBOT

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE alunos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    senha_hash TEXT NOT NULL,
    nome TEXT NOT NULL,
    lms_url_base TEXT,
    token_lms_cifrado BYTEA,
    lms_usuario_id BIGINT,
    estado_autorizacao TEXT NOT NULL DEFAULT 'pendente'
        CHECK (estado_autorizacao IN ('pendente', 'ativa', 'reautorizar')),
    canal_preferido TEXT NOT NULL DEFAULT 'telegram'
        CHECK (canal_preferido IN ('whatsapp', 'telegram')),
    fuso_horario TEXT NOT NULL DEFAULT 'America/Bahia',
    hora_resumo TIME NOT NULL DEFAULT '07:30',
    consentimento_em TIMESTAMPTZ,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    deletado_em TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_alunos_email ON alunos (lower(email)) WHERE deletado_em IS NULL;

CREATE TABLE identidades_canal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id UUID NOT NULL REFERENCES alunos (id) ON DELETE CASCADE,
    canal TEXT NOT NULL CHECK (canal IN ('whatsapp', 'telegram')),
    externo_id TEXT,
    codigo_pareamento_hash TEXT,
    codigo_expira_em TIMESTAMPTZ,
    verificado_em TIMESTAMPTZ,
    ultima_mensagem_in_em TIMESTAMPTZ,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_identidades_canal_externo UNIQUE (canal, externo_id)
);
CREATE INDEX idx_identidades_canal_codigo ON identidades_canal (codigo_pareamento_hash);

CREATE TABLE cursos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id UUID NOT NULL REFERENCES alunos (id) ON DELETE CASCADE,
    lms_curso_id BIGINT NOT NULL,
    nome TEXT NOT NULL,
    codigo TEXT,
    inicio_em TIMESTAMPTZ,
    fim_em TIMESTAMPTZ,
    ativa BOOLEAN NOT NULL DEFAULT TRUE,
    ultimo_sync_em TIMESTAMPTZ,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    deletado_em TIMESTAMPTZ,
    CONSTRAINT uq_cursos_aluno_lms UNIQUE (aluno_id, lms_curso_id)
);

CREATE TABLE itens_curso (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id UUID NOT NULL REFERENCES alunos (id) ON DELETE CASCADE,
    curso_id UUID NOT NULL REFERENCES cursos (id) ON DELETE CASCADE,
    tipo TEXT NOT NULL,
    externo_id TEXT NOT NULL,
    secao TEXT,
    titulo TEXT NOT NULL,
    url TEXT,
    prazo_em TIMESTAMPTZ,
    modificado_lms_em TIMESTAMPTZ,
    hash_conteudo TEXT NOT NULL,
    conteudo_texto TEXT,
    status TEXT NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'removido')),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    deletado_em TIMESTAMPTZ,
    CONSTRAINT uq_itens_curso_curso_externo UNIQUE (curso_id, externo_id)
);
CREATE INDEX idx_itens_curso_prazo ON itens_curso (aluno_id, prazo_em) WHERE prazo_em IS NOT NULL;

CREATE TABLE arquivos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id UUID NOT NULL REFERENCES alunos (id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES itens_curso (id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    mime TEXT NOT NULL,
    tamanho BIGINT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    versao INTEGER NOT NULL DEFAULT 1,
    texto_extraido_em TIMESTAMPTZ,
    erro_extracao TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    deletado_em TIMESTAMPTZ
);
CREATE INDEX idx_arquivos_aluno_sha256 ON arquivos (aluno_id, sha256);
CREATE INDEX idx_arquivos_item ON arquivos (item_id);

CREATE TABLE trechos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id UUID NOT NULL REFERENCES alunos (id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES itens_curso (id) ON DELETE CASCADE,
    arquivo_id UUID REFERENCES arquivos (id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    texto TEXT NOT NULL,
    contexto TEXT,
    embedding VECTOR(1024) NOT NULL,
    tsv TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('portuguese', coalesce(contexto, '') || ' ' || texto)
    ) STORED,
    modelo_emb TEXT NOT NULL,
    metadados JSONB NOT NULL DEFAULT '{}'::jsonb,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_trechos_embedding ON trechos USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_trechos_tsv ON trechos USING gin (tsv);
CREATE INDEX idx_trechos_aluno_item ON trechos (aluno_id, item_id);

CREATE TABLE execucoes_sync (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id UUID NOT NULL REFERENCES alunos (id) ON DELETE CASCADE,
    gatilho TEXT NOT NULL CHECK (gatilho IN ('agendado', 'manual')),
    iniciada_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalizada_em TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'executando'
        CHECK (status IN ('executando', 'sucesso', 'parcial', 'falha')),
    estatisticas JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_execucoes_sync_aluno ON execucoes_sync (aluno_id, iniciada_em DESC);

CREATE TABLE eventos_mudanca (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id UUID NOT NULL REFERENCES alunos (id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES itens_curso (id) ON DELETE CASCADE,
    execucao_id UUID REFERENCES execucoes_sync (id) ON DELETE SET NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('novo', 'alterado', 'removido')),
    detalhe JSONB NOT NULL DEFAULT '{}'::jsonb,
    detectado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    notificado_em TIMESTAMPTZ
);
CREATE INDEX idx_eventos_pendentes ON eventos_mudanca (aluno_id, detectado_em)
    WHERE notificado_em IS NULL;

CREATE TABLE resumos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id UUID NOT NULL REFERENCES alunos (id) ON DELETE CASCADE,
    periodo_ini TIMESTAMPTZ NOT NULL,
    periodo_fim TIMESTAMPTZ NOT NULL,
    texto TEXT NOT NULL,
    canal TEXT,
    enviado_em TIMESTAMPTZ,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE mensagens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id UUID NOT NULL REFERENCES alunos (id) ON DELETE CASCADE,
    canal TEXT NOT NULL,
    direcao TEXT NOT NULL CHECK (direcao IN ('in', 'out')),
    externo_id TEXT,
    texto TEXT NOT NULL,
    fontes JSONB,
    tokens_in INTEGER,
    tokens_out INTEGER,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_mensagens_canal_externo ON mensagens (canal, externo_id)
    WHERE externo_id IS NOT NULL;
CREATE INDEX idx_mensagens_aluno_data ON mensagens (aluno_id, criado_em DESC);

CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id UUID REFERENCES alunos (id) ON DELETE CASCADE,
    tipo TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    estado TEXT NOT NULL DEFAULT 'pendente'
        CHECK (estado IN ('pendente', 'executando', 'concluido', 'falhou', 'morto')),
    tentativas INTEGER NOT NULL DEFAULT 0,
    executar_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    bloqueado_ate TIMESTAMPTZ,
    erro TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_jobs_fila ON jobs (estado, executar_em);
"""


def upgrade() -> None:
    op.execute(SCHEMA)


def downgrade() -> None:
    op.execute(
        "DROP TABLE IF EXISTS jobs, mensagens, resumos, eventos_mudanca, execucoes_sync, "
        "trechos, arquivos, itens_curso, cursos, identidades_canal, alunos CASCADE"
    )
