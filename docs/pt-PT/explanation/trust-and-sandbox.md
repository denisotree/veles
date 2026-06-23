# Confiança e o sandbox

> 🌐 **Languages:** **English** · [Русский](../../ru/explanation/trust-and-sandbox.md)

O Veles executa um agente autónomo na sua máquina, pelo que restringe o que esse agente
pode fazer. Dois mecanismos trabalham em conjunto: uma **escada de confiança** para ações
sensíveis e um **sandbox** para o sistema de ficheiros. Para os comandos, consulte
[segurança e permissões](../how-to/security-and-permissions.md).

## A escada de confiança

Nem todas as ferramentas são iguais. Ler um ficheiro é inofensivo; executar um comando de
shell ou escrever em disco não é. As ferramentas sensíveis (`run_shell`, `write_file`,
`fetch_url`, …) param e pedem confirmação antes de correr, oferecendo quatro escolhas:

- **Uma vez** — permitir esta chamada única.
- **Sempre para este projeto** — persistir uma concessão de âmbito de projeto.
- **Sempre em todo o lado** — persistir uma concessão de âmbito de utilizador.
- **Recusar** — negá-la.

As concessões são guardadas para que não lhe seja perguntado de novo. Isto dá-lhe controlo
gradual: confie numa ferramenta uma vez, num projeto, ou globalmente — a sua escolha, feita
na primeira vez que importa.

### Ações de confirmação obrigatória

Algumas operações são suficientemente arriscadas para que o Veles as confirme **mesmo com
uma concessão**: eliminar ficheiros, obter URLs, instalar uma nova skill/ferramenta/módulo,
ligar um canal e escrever fora do projeto. Estas são viradas para o exterior ou difíceis de
reverter, pelo que uma concessão permanente não as deve cobrir silenciosamente.

### Segurança não interativa

Num daemon, em batch ou noutro contexto sem TTY não há humano a quem perguntar, pelo que o
Veles **recusa** ações sensíveis por omissão — um stdin perdido não pode infiltrar uma
aprovação. Para correr sem supervisão de propósito, abra uma janela de
[autopilot](../how-to/security-and-permissions.md#autopilot--a-time-boxed-bypass); cada ação
do autopilot é registada para revisão.

## O sandbox do sistema de ficheiros

Um guarda de caminhos limita onde as ferramentas podem ler e escrever:

- **Leitura** — dentro do projeto ativo (e dos seus subprojetos) mais `~/.veles/`.
- **Escrita** — apenas nas zonas graváveis do layout (por exemplo, `wiki/`); `.veles/` é
  sempre gravável para o estado da máquina.

Symlinks que escapam ao sandbox são rejeitados, e a travessia `..` é recusada antes da
resolução. As obtenções de URL mantêm uma lista de negação de SSRF. Configurações
avançadas podem sobrepor as raízes com `VELES_SANDBOX_ROOTS`, ou levantar o bloqueio de
rede privada com `VELES_FETCH_ALLOW_PRIVATE=1` — ambos opt-in.

## Porquê este design

O objetivo é **autonomia útil sem surpresas desagradáveis**: o agente pode fazer trabalho
real sem um pedido a cada leitura, mas qualquer coisa que possa danificar a sua máquina,
gastar dinheiro ou sair da caixa é controlada — uma vez, e depois recordada ao seu gosto.
