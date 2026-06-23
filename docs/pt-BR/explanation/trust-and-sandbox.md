# Confiança e o sandbox

> 🌐 **Idiomas:** **English** · [Русский](../../ru/explanation/trust-and-sandbox.md)

O Veles roda um agente autônomo na sua máquina, então ele restringe o que esse
agente pode fazer. Dois mecanismos trabalham juntos: uma **escada de confiança**
para ações sensíveis e um **sandbox** para o sistema de arquivos. Para os comandos,
veja [segurança e permissões](../how-to/security-and-permissions.md).

## A escada de confiança

Nem toda ferramenta é igual. Ler um arquivo é inofensivo; rodar um comando de shell
ou escrever em disco não é. Ferramentas sensíveis (`run_shell`, `write_file`,
`fetch_url`, …) param e perguntam antes de rodar, oferecendo quatro escolhas:

- **Uma vez** — permite esta única chamada.
- **Sempre para este projeto** — persiste uma concessão com escopo de projeto.
- **Sempre em todo lugar** — persiste uma concessão com escopo de usuário.
- **Recusar** — nega.

As concessões são armazenadas para que você não seja perguntado novamente. Isso lhe
dá controle gradual: confie em uma ferramenta uma vez, em um projeto ou globalmente
— sua escolha, feita na primeira vez que importa.

### Ações que sempre confirmam

Algumas operações são arriscadas o suficiente para que o Veles as confirme **mesmo
com uma concessão**: excluir arquivos, buscar URLs, instalar uma nova
skill/ferramenta/módulo, conectar um canal e escrever fora do projeto. Essas são
voltadas para fora ou difíceis de reverter, então uma concessão permanente não
deveria cobri-las silenciosamente.

### Segurança não interativa

Em um daemon, batch ou outro contexto sem TTY, não há humano para consultar, então
o Veles **recusa** ações sensíveis por padrão — um stdin perdido não consegue
introduzir uma aprovação às escondidas. Para rodar sem supervisão de propósito,
abra uma janela de [autopilot](../how-to/security-and-permissions.md#autopilot--a-time-boxed-bypass);
toda ação de autopilot é registrada para revisão.

## O sandbox do sistema de arquivos

Um guarda de caminhos limita onde as ferramentas podem ler e escrever:

- **Leitura** — dentro do projeto ativo (e seus subprojetos) mais `~/.veles/`.
- **Escrita** — apenas as zonas graváveis do layout (por exemplo, `wiki/`);
  `.veles/` é sempre gravável para estado de máquina.

Symlinks que escapam do sandbox são rejeitados, e a travessia `..` é recusada antes
da resolução. As buscas de URL mantêm uma deny-list de SSRF. Configurações
avançadas podem sobrescrever as raízes com `VELES_SANDBOX_ROOTS`, ou suspender o
bloqueio de rede privada com `VELES_FETCH_ALLOW_PRIVATE=1` — ambos por adesão.

## Por que este design

O objetivo é **autonomia útil sem surpresas desagradáveis**: o agente pode fazer
trabalho de verdade sem um prompt a cada leitura, mas qualquer coisa que possa
danificar sua máquina, gastar dinheiro ou sair da caixa é controlada — uma vez, e
depois lembrada conforme seu gosto.
