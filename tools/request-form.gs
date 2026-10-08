/**
 * Corrente — request form for people without a GitHub account.
 *
 * Run once in Google Apps Script (script.google.com → New project → paste →
 * Run "createRequestForm"). It creates, in the Google account that runs it:
 *   - a Google Form anyone can fill in without signing in;
 *   - a Google Sheet that receives the answers.
 * Nothing else: no triggers, no emails, no access to other files.
 * Steps for the owner, in Italian: docs/MODULO.md.
 *
 * The answers are read by Claude in the daily work session and published as
 * GitHub requests without any personal data (docs/MODULO.md).
 */

var FORM_TITLE = "Corrente — requests / richieste";
var SHEET_TITLE = "Corrente — requests (answers)";
var GITHUB_ISSUES = "https://github.com/MichaelPito/ha-corrente/issues";

function createRequestForm() {
  var form = FormApp.create(FORM_TITLE);
  form.setDescription(
    "Ask for a change, report a problem or ask us to add your operator or tariff. " +
      "No account needed. / Chiedi una modifica, segnala un problema o chiedici di " +
      "aggiungere il tuo gestore o la tua tariffa. Non serve un account.\n" +
      "Deutsch und Français willkommen.\n\n" +
      "Privacy: please do not write personal data (name, address, e-mail, customer " +
      "number). We publish each request on GitHub without any personal data. / Per " +
      "favore non scrivere dati personali (nome, indirizzo, e-mail, numero cliente): " +
      "pubblichiamo ogni richiesta su GitHub senza dati personali."
  );
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setLimitOneResponsePerUser(false); // would force respondents to sign in
  form.setPublishingSummary(false);
  form.setShowLinkToRespondAgain(true);
  form.setConfirmationMessage(
    "Thank you! We publish requests on GitHub, without personal data, usually within " +
      "a few days: " + GITHUB_ISSUES + "\n" +
      "Grazie! Pubblichiamo le richieste su GitHub, senza dati personali, di solito " +
      "entro pochi giorni: " + GITHUB_ISSUES
  );

  form
    .addMultipleChoiceItem()
    .setTitle("What is it about? / Di cosa si tratta?")
    .setChoiceValues([
      "Something does not work / Qualcosa non funziona",
      "Idea or change / Idea o modifica",
      "Add my operator or tariff / Aggiungete il mio gestore o la mia tariffa",
      "Question / Domanda",
    ])
    .setRequired(true);

  form
    .addMultipleChoiceItem()
    .setTitle("Country / Paese")
    .setChoiceValues(["Switzerland / Svizzera", "Italy / Italia"])
    .showOtherOption(true)
    .setRequired(true);

  form
    .addParagraphTextItem()
    .setTitle("Tell us more / Raccontaci")
    .setHelpText(
      "What happened, or what would you like? / Cosa è successo, o cosa ti piacerebbe?"
    )
    .setValidation(
      FormApp.createParagraphTextValidation().requireTextLengthLessThanOrEqualTo(3000).build()
    )
    .setRequired(true);

  form
    .addTextItem()
    .setTitle(
      "Operator, municipality or contract (optional) / Gestore, comune o contratto (facoltativo)"
    )
    .setHelpText("For example: AIL, Lugano, 'Casa giorno-notte' · Enel, PUN + spread");

  form
    .addTextItem()
    .setTitle(
      "Home Assistant and Corrente versions (optional) / Versioni di Home Assistant e Corrente (facoltativo)"
    )
    .setHelpText("Settings → About · Impostazioni → Informazioni");

  // New forms are published by default; make sure, where Google supports the setting.
  if (form.supportsAdvancedResponderPermissions() && !form.isPublished()) {
    form.setPublished(true);
  }

  var sheet = SpreadsheetApp.create(SHEET_TITLE);
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  Logger.log("Form for people (share this): " + form.getPublishedUrl());
  Logger.log("Answers sheet (private): " + sheet.getUrl());
}
