// État du tri actuellement affiché dans la popup
let etatTri = {
  cle: null,      // "rarete" | "points" | "constellation" | null
  direction: 1    // 1 = croissant, -1 = décroissant
};

// Données du personnage courant affichées dans la popup (pour pouvoir re-trier sans refetch)
let personnagesAffiches = [];

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

function getFondRarete(rarete) {
  const valeur = String(rarete);

  if (valeur === "5") {
    return "../DB/images/others/bg_5_star.webp";
  }

  if (valeur === "3") {
    return "../DB/images/others/bg_3_star.webp";
  }

  return "../DB/images/others/bg_4_star.webp";
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

// ---- Tri ----

function trierPersonnages(liste) {
  if (!etatTri.cle) {
    return liste;
  }

  const copie = [...liste];

  copie.sort((a, b) => {
    let valA;
    let valB;

    if (etatTri.cle === "rarete") {
      valA = Number(a.item.rarete) || 0;
      valB = Number(b.item.rarete) || 0;
    } else if (etatTri.cle === "points") {
      valA = Number(a.item.PPC?.[a.valeur] ?? 0);
      valB = Number(b.item.PPC?.[b.valeur] ?? 0);
    } else if (etatTri.cle === "constellation") {
      valA = a.valeur;
      valB = b.valeur;
    } else {
      return 0;
    }

    return (valA - valB) * etatTri.direction;
  });

  return copie;
}

function mettreAJourBoutonsTri() {
  document.querySelectorAll(".sort-btn").forEach(btn => {
    const cle = btn.dataset.sort;
    const fleche = btn.querySelector(".fleche");

    if (cle === etatTri.cle) {
      btn.classList.add("active");
      fleche.textContent = etatTri.direction === 1 ? "▲" : "▼";
    } else {
      btn.classList.remove("active");
      fleche.textContent = "";
    }
  });
}

function creerCarteProfilPersonnage(personnage, valeur) {
  const card = document.createElement("div");
  card.className = "character-card";

  const fond = getFondRarete(personnage.rarete);

  card.innerHTML = `
    <div class="character-visuel" style="background-image: url('${fond}');">
      <img src="../DB/${personnage.image}" alt="${personnage.nom}">
      <div class="character-ppc-badge">${personnage.PPC?.[valeur] ?? ""}</div>
    </div>
    <div class="character-name">${personnage.nom}</div>
    <div class="character-level">${getLabelConstellation(valeur)}</div>
  `;

  return card;
}

function rendreProfilBox() {
  const container = document.getElementById("profile-box");
  container.innerHTML = "";

  const listeTriee = trierPersonnages(personnagesAffiches);

  listeTriee.forEach(({ item, valeur }) => {
    container.appendChild(creerCarteProfilPersonnage(item, valeur));
  });
}

function initialiserBarreTri() {
  document.querySelectorAll(".sort-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const cle = btn.dataset.sort;

      if (etatTri.cle === cle) {
        // Même bouton recliqué : on inverse la direction
        etatTri.direction *= -1;
      } else {
        // Nouveau critère : on repart en croissant
        etatTri.cle = cle;
        etatTri.direction = 1;
      }

      mettreAJourBoutonsTri();
      rendreProfilBox();
    });
  });
}

// ---- Ouverture / fermeture popup ----

async function ouvrirProfil(discordId, nom) {
  try {
    const [profil, personnages] = await Promise.all([
      chargerProfil(discordId),
      chargerPersonnages()
    ]);

    const fullBox = profil.data?.characters?.full || {};

    personnagesAffiches = personnages
      .filter(p => (fullBox[p.id] ?? -1) >= 0)
      .map(p => ({ item: p, valeur: fullBox[p.id] }));

    // Réinitialise le tri à chaque ouverture de profil
    etatTri = { cle: null, direction: 1 };
    mettreAJourBoutonsTri();

    document.getElementById("modal-title").textContent = `Box full de ${nom}`;
    rendreProfilBox();
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
    initialiserBarreTri();
  } catch (error) {
    console.error(error);
    alert("Erreur lors du chargement des comptes.");
  }
}

demarrer();