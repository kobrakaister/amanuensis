PROMPTS = {
    "it": {
        "system": (
            "Sei un assistente di studio universitario. Scrivi solo in italiano, in Markdown. "
            "Usa soltanto il contenuto della lezione fornita e non aggiungere informazioni esterne."
        ),
        "notes": (
            "Questa è una parte della trascrizione di una lezione. Ogni riga inizia con il tempo [hh:mm:ss].\n"
            "Scrivi appunti di studio organizzati per argomento. Per ogni argomento usa un titolo che inizia con '## ' "
            "e sotto un elenco di punti, uno per idea. "
            "Termina ogni punto, sulla stessa riga, con l'orario copiato da una riga della trascrizione, nel formato [hh:mm:ss]. "
            "Non inventare orari e non lasciare un orario da solo. "
            "Non scrivere introduzioni né conclusioni.\n\nTrascrizione:\n{text}"
        ),
        "notes_repair": (
            "Questi appunti non hanno l'orario su ogni punto. Riscrivili con lo stesso contenuto. "
            "Mantieni i titoli che iniziano con '## '. "
            "Ogni punto deve finire con un orario [hh:mm:ss] copiato da una riga della trascrizione. "
            "Non inventare orari.\n\nAppunti:\n{notes}\n\nTrascrizione:\n{text}"
        ),
        "mindmap": (
            "Costruisci la mappa mentale della lezione a partire da questi appunti. "
            "Rispondi solo con una gerarchia Markdown: una prima riga '# ' con il titolo della lezione, "
            "'## ' per i temi principali, '### ' per i sottotemi ed elenchi puntati per i dettagli. "
            "Non superare quattro livelli e non aggiungere testo fuori dalla gerarchia.\n\nAppunti:\n{text}"
        ),
        "questions": (
            "Scrivi da 10 a 20 domande di ripasso basate su questi appunti, dalle definizioni ai collegamenti "
            "fra concetti. Per ogni domanda usa esattamente questo formato:\n\n"
            "### 1. <domanda>\nRisposta attesa: <risposta in due o tre frasi>\nRiferimento: [hh:mm:ss]\n\n"
            "Appunti:\n{text}"
        ),
        "notes_title": "# Appunti",
        "questions_title": "# Domande di ripasso",
    },
    "en": {
        "system": (
            "You are a university study assistant. Write only in English, in Markdown. "
            "Use only the content of the lecture provided and do not add outside information."
        ),
        "notes": (
            "This is part of a lecture transcript. Each line starts with the time [hh:mm:ss].\n"
            "Write study notes organised by topic. For each topic use a heading starting with '## ' "
            "followed by one bullet per idea. "
            "End each bullet, on the same line, with the time copied from a transcript line, in the format [hh:mm:ss]. "
            "Do not invent times and do not leave a time on its own line. "
            "Do not write an introduction or a conclusion.\n\nTranscript:\n{text}"
        ),
        "notes_repair": (
            "These notes do not put a time on every point. Rewrite them with the same content. "
            "Keep headings that start with '## '. "
            "End every point with a time [hh:mm:ss] copied from a transcript line. "
            "Do not invent times.\n\nNotes:\n{notes}\n\nTranscript:\n{text}"
        ),
        "mindmap": (
            "Build the mind map of the lecture from these notes. "
            "Reply only with a Markdown hierarchy: a first line '# ' with the lecture title, "
            "'## ' for the main themes, '### ' for subthemes and bulleted lists for details. "
            "Use at most four levels and add no text outside the hierarchy.\n\nNotes:\n{text}"
        ),
        "questions": (
            "Write 10 to 20 review questions based on these notes, from definitions to connections between "
            "concepts. For each question use exactly this format:\n\n"
            "### 1. <question>\nExpected answer: <answer in two or three sentences>\nReference: [hh:mm:ss]\n\n"
            "Notes:\n{text}"
        ),
        "notes_title": "# Notes",
        "questions_title": "# Review questions",
    },
}
