async function chargerComptes() {
  const reponse = await fetch("/api/accounts");
  if (!reponse.ok) {
    throw new Error("Impossible de charger les comptes.");
  }
  return await reponse.json();
}

async function chargerPersonnages() {
  const reponse = await fetch("../DB/characters.json");
  if (!reponse.ok) {
    throw new Error("Impossible de charger les personnages.");
  }
  return await reponse.json();
}

async function chargerProfil(discordId) {
  const reponse = await fetch(`/api/accounts/${discordId}`);
  if (!reponse.ok) {
    throw new Error("Impossible de charger le profil.");
  }
  return await reponse.json();
}

function getLabelConstellation(valeur) {
  if (valeur < 0) return "";
  return `C${valeur}`;
}

function afficherComptes(comptes) {
  const liste = document.getElementById("accounts-list");
  liste.innerHTML = "";

  comptes.forEach(compte => {
    const card = document.createElement("div");
    card.className = "account-card";
    card.dataset.id = compte.discord_id;

    const nom = compte.discord_global_name || compte.discord_username || "Utilisateur inconnu";
    const username = compte.discord_username ? `@${compte.discord_username}` : "";

    card.innerHTML = `
      <img src="${compte.discord_avatar_url || ""}" alt="${nom}">
      <div>
        <div class="account-name">${nom}</div>
        <div class="account-sub">${username}</div>
      </div>
    `;

    card.addEventListener("click", () => ouvrirProfil(compte.discord_id, nom));
    liste.appendChild(card);
  });
}

function afficherBoxFull(profil, personnages) {
  const container = document.getElementById("profile-box");
  container.innerHTML = "";

  const fullBox = profil.data?.characters?.full || {};

  const personnagesPossedes = personnages.filter(p => (fullBox[p.id] ?? -1) >= 0);

  personnagesPossedes.forEach(personnage => {
    const valeur = fullBox[personnage.id];
    const card = document.createElement("div");
    card.className = "character-card";

    card.innerHTML = `
      <img src="../DB/${personnage.image}" alt="${personnage.nom}">
      <div class="character-name">${personnage.nom}</div>
      <div class="character-level">${getLabelConstellation(valeur)}</div>
    `;

    container.appendChild(card);
  });
}

async function ouvrirProfil(discordId, nom) {
  try {
    const [profil, personnages] = await Promise.all([
      chargerProfil(discordId),
      chargerPersonnages()
    ]);

    document.getElementById("modal-title").textContent = `Box full de ${nom}`;
    afficherBoxFull(profil, personnages);
    document.getElementById("modal").classList.add("active");
  } catch (error) {
    console.error(error);
    alert("Erreur lors du chargement du profil.");
  }
}

function initialiserModal() {
  const modal = document.getElementById("modal");
  const closeBtn = document.getElementById("close-modal");

  closeBtn.addEventListener("click", () => {
    modal.classList.remove("active");
  });

  modal.addEventListener("click", event => {
    if (event.target === modal) {
      modal.classList.remove("active");
    }
  });
}

async function demarrer() {
  try {
    const comptes = await chargerComptes();
    afficherComptes(comptes);
    initialiserModal();
  } catch (error) {
    console.error(error);
    alert("Erreur lors du chargement des comptes.");
  }
}

demarrer();