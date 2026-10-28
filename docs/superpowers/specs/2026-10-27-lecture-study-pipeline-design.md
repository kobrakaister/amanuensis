# Pipeline locale per lo studio delle lezioni

Data: 2026-10-27

## Scopo

Trasformare registrazioni lunghe di lezioni universitarie in un pacchetto di studio per ogni lezione: trascrizione con tempi, appunti strutturati, mappa mentale e domande di ripasso.

La prima versione elabora una lezione alla volta su questo PC. L'audio non viene inviato a servizi esterni e il file originale resta nel percorso scelto dall'utente.

## Decisioni

- Le lezioni sono soprattutto in italiano; una lezione può essere in inglese.
- Trascrizione locale con faster-whisper e il modello Whisper large-v3, eseguito sulla GPU NVIDIA RTX PRO 2000 Blackwell da 8 GB.
- Sintesi locale con Ollama e un modello da 7–8 miliardi di parametri. Il valore iniziale è `qwen2.5:7b`, configurabile in un solo punto.
- Il modello linguistico sta dietro un'interfaccia. La prima versione contiene solo l'implementazione Ollama.
- L'avvio avviene osservando una cartella configurata. Non ci sono pagina web né comandi da ricordare per ogni file.
- La trascrizione è un unico testo con i tempi, senza separazione dei parlanti.
- Docker e la sintesi cloud del testo restano fuori dalla prima versione.

## Flusso dei file

Il repository è dentro OneDrive. Le registrazioni e i risultati stanno fuori da OneDrive, fuori dal repository e fuori dalle condivisioni di rete come `R:`. I percorsi sono configurabili. I valori iniziali sono:

- cartella osservata: `C:\Users\Mathia.Scucchiari\mba-studio\lezioni`
- archivio risultati: `C:\Users\Mathia.Scucchiari\mba-studio\library`

All'avvio il sistema rifiuta una cartella osservata o un archivio che si trovano dentro OneDrive o su un disco di rete.

Il sistema non sposta e non modifica la registrazione. L'identità di una lezione è l'hash SHA-256 del contenuto. Il nome del file non identifica la lezione. Durante la preparazione crea un WAV di lavoro dentro `work\` e lo elimina dopo una trascrizione riuscita; questo WAV non entra nell'archivio come copia della registrazione.

```text
C:\Users\Mathia.Scucchiari\mba-studio\lezioni\2026-10-27-strategia.m4a      resta qui
        |
        v
SHA-256 del contenuto
        |
        v
C:\Users\Mathia.Scucchiari\mba-studio\library\<hash>\
        |-- state.json
        |-- source.json
        |-- work\                 temporaneo, rimosso dopo la trascrizione
        |-- transcript.md
        |-- transcript.json
        |-- notes.md
        |-- mindmap.md
        |-- questions.md
        `-- report.md
```

`source.json` conserva il percorso assoluto, hash, dimensione, durata, lingua rilevata e misure audio. Se il file viene rinominato o spostato dentro la cartella osservata, il sistema aggiorna il percorso e non ripete il lavoro. Lo stesso contenuto in due percorsi produce un solo pacchetto.

Una fase è completa solo dopo che il suo risultato è stato scritto in un file temporaneo e rinominato nella posizione finale. Solo allora `state.json` avanza. Un riavvio ripete esclusivamente la fase non completata. Se `state.json` manca, i file finali già presenti contano come fasi complete.

## Fasi

Lo scanner percorre anche le sottocartelle della cartella osservata. L'estensione, confrontata senza distinzione di maiuscole, decide se il file entra in coda. ffmpeg legge il contenitore e la preparazione produce sempre lo stesso WAV mono a 16 kHz. Un file con estensione accettata ma non decodificabile resta `failed`, senza nuovi tentativi.

Estensioni accettate:

- `.wav`, `.aiff`, `.aif`: PCM, comprese le esportazioni iOS.
- `.caf`: registratori iOS che usano il contenitore Core Audio, con PCM o ALAC. Questa build di ffmpeg non scrive AAC dentro un CAF; un CAF che non si lascia decodificare resta `failed`.
- `.mp3`.
- `.m4a`, `.mp4`, `.aac`: Memo Vocali di iOS e i registratori Android che usano AAC, compreso ALAC dentro `.m4a`.
- `.3gp`, `.3gpp`, `.amr`: registratore Android storico, in AMR.
- `.ogg`, `.opus`, `.webm`: registratori Android più recenti, in Opus o Vorbis.
- `.flac`: già previsto, anche se non è un formato tipico del telefono.

Elabora una lezione alla volta, nell'ordine in cui i file sono diventati stabili.

1. **Accettazione.** Lo scanner ignora un file finché dimensione e data di modifica non restano stabili per 30 secondi. Calcola l'hash, legge durata e formato con ffprobe e verifica lo spazio libero.
2. **Analisi.** Misura l'energia fra 20 e 80 Hz e quella fra 80 e 300 Hz.
3. **Preparazione.** Converte l'audio in WAV mono a 16 kHz. Applica un passa-alto a 80 Hz solo se la misura lo richiede. Rimuove il WAV al termine della trascrizione riuscita.
4. **Trascrizione.** faster-whisper produce segmenti con tempi di inizio e fine. Il rilevamento della lingua usa il primo minuto. Se la lingua rilevata è italiano o inglese e la probabilità è almeno 0,80, usa quella lingua. In ogni altro caso usa l'italiano. La lingua scelta e la probabilità vengono scritte in `source.json` e nel report.
5. **Studio.** I segmenti vengono raggruppati in blocchi di al massimo 12 minuti. Gli ultimi 30 secondi di un blocco vengono ripetuti all'inizio del blocco successivo. Ollama produce appunti, mappa e domande nella lingua scelta per la trascrizione.

Prima della preparazione serve spazio libero pari almeno al doppio del WAV stimato, calcolato come 32.000 byte per secondo di durata. Se lo spazio manca, la fase non inizia e il report indica la quantità richiesta.

## Filtro passa-alto

Il filtro iniziale è `highpass=f=80`. Viene applicato quando il rapporto fra l'energia 20–80 Hz e l'energia 80–300 Hz è maggiore o uguale a 1. La soglia è un unico valore di configurazione. Il report registra le due misure, il rapporto, la soglia e la decisione. Il filtro non è un denoise generale: il rumore a banda larga resta nel segnale e viene segnalato nel report quando il rapporto è basso.

## Risultati di studio

- `transcript.md`: testo leggibile con i tempi dei segmenti.
- `transcript.json`: segmenti, tempi, lingua e modello di trascrizione.
- `notes.md`: appunti organizzati per argomenti, con i riferimenti ai tempi della trascrizione.
- `mindmap.md`: gerarchia Markdown apribile con Markmap.
- `questions.md`: domande di ripasso con la risposta attesa e il riferimento al tempo.
- `report.md`: misure, decisioni, modello, tentativi, avvertimenti ed esito.

## Errori e tentativi

| Situazione | Esito |
|---|---|
| File ancora in copia | Attesa dei 30 secondi di stabilità |
| Audio illeggibile o formato non riconosciuto | `failed`, senza nuovi tentativi automatici |
| Filtro non applicabile o preparazione del filtro non riuscita | Trascrizione dell'audio normalizzato e annotazione nel report |
| GPU occupata, memoria video esaurita, Ollama irraggiungibile, modello assente o timeout | Fino a 5 ripetizioni della chiamata |
| Risposta del modello vuota o priva delle sezioni richieste | Un nuovo tentativo di generazione, poi `needs_review` |
| Registrazione assente dalla cartella osservata | Pausa, con risultati parziali conservati |
| Spazio disco insufficiente | `waiting`, con lo spazio richiesto nel report; la scansione successiva riprova la fase |

Una chiamata che fallisce per un errore temporaneo viene ripetuta fino a 5 volte; prima delle ripetizioni attende 15, 30, 60, 120 e 240 secondi. Se la memoria video si esaurisce per due volte, le esecuzioni successive della trascrizione usano la CPU. Il report registra il passaggio. Dopo la quinta ripetizione la fase resta `waiting`: la scansione successiva riprova quella fase e non ripete le fasi complete.

`needs_review` conserva il testo parziale. Lo scanner non ritenta da solo né `needs_review` né `failed`. Per ripeterli si elimina `state.json`: i file finali già presenti dimostrano le fasi complete e il lavoro riprende dalla prima fase senza il proprio file finale. I log contengono percorso, hash, fase ed esito, e non contengono il testo della lezione.

## Componenti

- **Scanner:** trova i file stabili e associa l'hash al percorso corrente.
- **Archivio lavori:** legge e scrive `state.json` e i risultati.
- **Analizzatore audio:** calcola il rapporto fra le due bande.
- **Preparatore:** produce il WAV e applica il filtro secondo la decisione ricevuta.
- **Trascrittore:** interfaccia con un'implementazione faster-whisper.
- **Compositore di studio:** costruisce appunti, mappa e domande attraverso l'interfaccia del modello.
- **Client Ollama:** unica implementazione del modello nella prima versione.
- **Esecutore:** esegue la prima fase incompleta e applica la politica dei tentativi.

Whisper e Ollama si sostituiscono nei test senza avviare i modelli.

## Verifiche

I test automatici controllano:

- l'applicazione del passa-alto alla soglia e la sua esclusione sotto la soglia;
- l'avanzamento dello stato solo dopo il rename del risultato;
- la ripresa dall'ultima fase incompleta, compresa la sintesi quando la trascrizione è già presente;
- le cinque ripetizioni e il passaggio alla CPU dopo il secondo esaurimento della memoria video;
- l'assenza di un nuovo tentativo automatico per un file illeggibile;
- la conservazione del parziale nello stato `needs_review`.

Un WAV sintetico di pochi secondi attraversa accettazione, analisi e preparazione. La prova con una registrazione reale e i modelli installati è un controllo manuale, separato dai test automatici.

## Fuori dalla prima versione

Separazione dei parlanti, pagina web, Docker, invio dell'audio o del testo a un servizio cloud, domande interattive sull'insieme delle lezioni e riduzione del rumore a banda larga.

## Esito atteso

Copiando una registrazione nella cartella osservata, senza fare altro, il sistema produce `transcript.md`, `transcript.json`, `notes.md`, `mindmap.md`, `questions.md` e `report.md`, oltre a `source.json` e `state.json`. Una seconda esecuzione sullo stesso contenuto non ripete le fasi che hanno già il file finale. Un'interruzione durante la sintesi conserva la trascrizione e riprende dagli appunti.
