# Eval set draft — 40 segments (gold labels pending review)
Format: one segment per block. Edit freely.

## clean-01  [clean]
EN: Save your changes before closing the window.
MT: Salve as alterações antes de fechar a janela.
Glossary: save→salvar, window→janela
- (clean — no findings)

## clean-02  [clean]
EN: Your session will expire in {0} minutes.
MT: A sua sessão expirará em {0} minutos.
Glossary: session→sessão
- (clean — no findings)

## clean-03  [clean]
EN: Click the link below to reset your password.
MT: Clique no link abaixo para redefinir sua senha.
Glossary: password→senha
- (clean — no findings)

## clean-04  [clean]
EN: No records match the selected filters.
MT: Nenhum registro corresponde aos filtros selecionados.
Glossary: record→registro
- (clean — no findings)

## clean-05  [clean]  (HOLD-OUT)
EN: Upload a file of type .csv, .xlsx or .pdf (max 10 MB).
MT: Carregue um arquivo do tipo .csv, .xlsx ou .pdf (máx. 10 MB).
Glossary: file→arquivo, upload→carregar
- (clean — no findings)

## clean-06  [clean]
EN: The invoice has been sent to the customer's e-mail address.
MT: A fatura foi enviada para o endereço de e-mail do cliente.
Glossary: invoice→fatura, customer→cliente
- (clean — no findings)

## clean-08  [clean]
EN: Connection to the server was interrupted. Try again later.
MT: A conexão com o servidor foi interrompida. Tente novamente mais tarde.
Glossary: connection→conexão, server→servidor
- (clean — no findings)

## clean-09  [clean]
EN: You have %d pending approval requests.
MT: Você tem %d solicitações de aprovação pendentes.
Glossary: request→solicitação
- (clean — no findings)

## clean-10  [clean]
EN: Learn more about data privacy at https://example.com/privacy
MT: Saiba mais sobre privacidade de dados em https://example.com/privacy
- (clean — no findings)

## acc-01  [accuracy]
EN: The license expires on 30/11/2026 for 12 users.
MT: A licença expira em 30/11/2026.
Glossary: license→licença
- [critical/accuracy] “A licença expira em 30/11/2026.” — Omission: 'for 12 users' not translated.

## acc-02  [accuracy]
EN: Do not disable this option unless instructed by support.
MT: Desative esta opção, a menos que seja orientado pelo suporte.
Glossary: option→opção
- [critical/accuracy] “Desative esta opção” — Mistranslation: negation 'Do not disable' rendered as imperative 'Desative' — meaning inverted.

## acc-03  [accuracy]
EN: Export up to 5,000 rows per request.
MT: Exporte até 500 linhas por solicitação.
Glossary: request→solicitação
- [critical/accuracy] “500” — Number altered: source says 5,000, MT says 500.

## acc-04  [accuracy]  (HOLD-OUT)
EN: The report includes last quarter's data.
MT: O relatório inclui os dados do trimestre atual.
Glossary: report→relatório
- [critical/accuracy] “trimestre atual” — Mistranslation: 'last quarter' rendered as 'current quarter'.

## acc-05  [accuracy]
EN: Message deleted by author.
MT: Mensagem excluída pelo autor. Esta ação é permanente.
- [major/accuracy] “Esta ação é permanente.” — Addition: sentence not present in source.

## acc-06  [accuracy]
EN: Hello {0}, {1} added you to team "{2}".
MT: Olá {0}, foi adicionado à equipe.
Glossary: team→equipe
- [major/accuracy] “{1}” — Placeholder {1} dropped.
- [major/accuracy] “{2}” — Placeholder {2} and team name dropped.

## acc-07  [accuracy]
EN: Shipping is free for orders over $99.
MT: O frete é grátis para pedidos acima de R$99.
- [critical/accuracy] “R$99” — Currency changed from USD ($) to BRL (R$) without instruction.

## acc-08  [accuracy]  (HOLD-OUT)
EN: Your file could not be processed. Error code: 4221
MT: O arquivo foi processado com sucesso.
Glossary: file→arquivo
- [critical/accuracy] “O arquivo foi processado com sucesso.” — Mistranslation: error message rendered as success message; error code 4221 dropped.
- [critical/accuracy] “O arquivo foi processado com sucesso.” — Omission: error code 4221 missing.

## acc-09  [accuracy]
EN: the update will restart the application
MT: the update will restart the application
- (no glossary: an untranslated string must be caught without one)
- [major/accuracy] "the update will restart the application" — Untranslated: MT is identical to the English source.

## term-01  [terminology]
EN: Upload the supporting document.
MT: Carregue o documento comprovativo.
Glossary: supporting document→comprovante
- [moderate/terminology] “documento comprovativo” — PT-BR expects 'comprovante'; 'documento comprovativo' is EU usage.

## term-02  [terminology]  (HOLD-OUT)
EN: Delete the user account permanently.
MT: Suprima a conta de usuário definitivamente.
Glossary: delete→excluir
- [major/terminology] “Suprima” — Glossary requires 'excluir' for 'delete'; 'suprimir' is not the approved term.

## term-03  [terminology]
EN: The download link will expire in 24 hours.
MT: A ligação de descarregamento expira em 24 horas.
Glossary: download→baixar, link→link
- [major/terminology] “ligação” — Glossary requires 'link'; 'ligação' is EU for hyperlink.
- [major/terminology] “descarregamento” — Glossary requires 'baixar' family for 'download'; 'descarregamento' is EU.

## term-04  [terminology]
EN: Configure your e-mail signature.
MT: Configure sua assinatura de e-mail.
Glossary: e-mail→e-mail, configure→configurar
- (clean — no findings)

## term-05  [terminology]  (HOLD-OUT)
EN: The administrator assigned you a new role.
MT: O administrador atribuiu-lhe um novo perfil.
Glossary: administrator→administrador, role→função
- [major/terminology] “perfil” — Glossary requires 'função' for 'role'; 'perfil' is the incorrect term.

## term-06  [terminology]
EN: Log out from all devices.
MT: Termine sessão em todos os dispositivos.
Glossary: log out→sair
- [moderate/terminology] “Termine sessão” — Glossary requires 'sair' for 'log out'; 'terminar sessão' is EU-calqued.

## term-07  [terminology]
EN: Enter your username and licence key.
MT: Introduza o nome de usuário e a chave de licença.
Glossary: username→nome de usuário, licence key→chave de licença
- [moderate/terminology] “Introduza” — PT-BR UI convention is 'Insira'/'Digite'; 'introduzir' for data entry is EU.

## term-08  [terminology]
EN: The usertype cannot be empty.
MT: O tipo de utilizador não pode estar vazio.
Glossary: usertype→tipo de usuário
- [moderate/terminology] "tipo de utilizador" — Glossary maps 'usertype' to a fixed term; MT used the PT-EU rendering 'utilizador'.

## term-09  [terminology]
EN: Call us on your mobile during business hours.
MT: Contacte-nos através do seu  telemóvel durante o horário comercial.
Glossary: mobile→celular, business hours→horário comercial
- [moderate/terminology] "telemóvel" — PT-EU word; PT-BR expects 'celular' (also a glossary violation: both checks fire on this span, report it once).
- [minor/style] "seu  telemóvel" — Double space between words.

## flu-01  [fluency]  (HOLD-OUT)
EN: Are you sure you want to discard these changes?
MT: Você tem certeza que você quer descartar estas mudanças?
Glossary: change→alteração
- [moderate/fluency] “Você tem certeza que você quer” — Redundant repeated subject; unnatural. Prefer 'Tem certeza de que deseja'.
- [minor/terminology] “mudanças” — Style guide prefers 'alterações' for software 'changes'.

## flu-02  [fluency]
EN: This action cannot be undone.
MT: Esta ação não pode ser desfeita ser.
Glossary: action→ação
- [major/fluency] “desfeita ser” — Ungrammatical duplicated 'ser'; broken verb construction.

## flu-03  [fluency]
EN: We couldn't find any results for your search.
MT: Nós não poderíamos encontrar quaisquer resultados para sua pesquisa.
Glossary: search→pesquisa
- [moderate/fluency] “Nós não poderíamos encontrar quaisquer resultados” — Calque from English; unnatural PT-BR. Prefer 'Não encontramos resultados para sua pesquisa'.

## flu-04  [fluency]
EN: Drag the field here to add it to the form.
MT: Arraste o campo aqui para adicionar ele ao formulário.
Glossary: field→campo, form→formulário
- [minor/fluency] “adicionar ele” — Colloquial object pronoun 'ele'; standard UI register expects 'adicioná-lo'.

## flu-05  [fluency]  (HOLD-OUT)
EN: Only administrators can view this page.
MT: Somente administradores pode visualizar esta página.
Glossary: administrator→administrador
- [major/fluency] “administradores pode” — Subject-verb disagreement: plural subject with singular verb.

## flu-06  [fluency]
EN: Failed to synchronize contacts. Reason: quota exceeded.
MT: Falhou para sincronizar contatos. Motivo: cota excedida.
Glossary: contact→contato
- [major/fluency] “Falhou para sincronizar” — Calque of 'failed to'; PT-BR expects 'Falha ao sincronizar'.

## sty-01  [style]
EN: Thank you for your feedback!
MT: Agradecemos pelo vosso feedback!
Glossary: feedback→feedback
- [moderate/style] “vosso” — 'Vosso' is not used in PT-BR product copy; use 'seu'.

## sty-02 [style] (HOLD-OUT) — politeness
EN: Delete the selected item?
MT: Por favor, exclua o item selecionado.
Glossary: delete→excluir
- [minor/style] "Por favor," — Courtesy formula added to a short destructive confirmation; PT-BR UI copy omits it.

## sty-03 [style] — capitalization
EN: Your recent activity
MT: Sua Atividade Recente
Glossary: activity→atividade
- [minor/style] "Sua Atividade Recente" — Heading uses English title case; PT-BR uses sentence case, 'Sua atividade recente'.

## sty-04 [style] (HOLD-OUT) — address consistency
EN: You can change your profile photo. Only you can see it.
MT: Podes alterar a tua foto de perfil. Só você pode vê-la.
- [moderate/style] "Só você pode vê-la" — Address switches from tu (podes, tua) to você mid-segment.

## sty-05 [style] — punctuation, deterministic
EN: Password must contain at least 8 characters.
MT: A senha deve conter pelo menos 8 caracteres..
Glossary: password→senha
- [minor/style] "caracteres.." — Doubled final period.

## sty-06 [style] — two findings
EN: Please try again later.
MT: Por favor, tente novamente mais tarde!
- [minor/style] "Por favor," — Courtesy formula in an error message; PT-BR error copy is neutral.
- [minor/style] "mais tarde!" — Exclamation mark inappropriate for an error message.

## sty-07  [style]  (HOLD-OUT)
EN: The report was generated with success
MT: O relatório foi gerado com sucesso
Glossary: report→relatório
- [minor/style] “gerado com sucesso” — Missing final period.
