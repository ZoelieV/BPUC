const iconesElements = {
  pyro: "../DB/images/others/pyro.webp",
  hydro: "../DB/images/others/hydro.webp",
  anemo: "../DB/images/others/anemo.webp",
  electro: "../DB/images/others/electro.webp",
  cryo: "../DB/images/others/cryo.webp",
  dendro: "../DB/images/others/dendro.webp",
  geo: "../DB/images/others/geo.webp"
};

const iconesTypesArmes = {
  sword: "../DB/images/others/sword.webp",
  claymore: "../DB/images/others/claymore.webp",
  polearm: "../DB/images/others/polearm.webp",
  bow: "../DB/images/others/bow.webp",
  catalyst: "../DB/images/others/catalyst.webp"
};

const configCollections = {
  characters: {
    pointsField: "PPC",
    labels: ["C0", "C1", "C2", "C3", "C4", "C5", "C6"],
    nomVue: "Personnages"
  },
  weapons: {
    pointsField: "PPW",
    labels: ["R1", "R2", "R3", "R4", "R5"],
    nomVue: "Armes"
  }
};

// État courant de la popup
let vueActive = "characters";   // "characters" | "weapons"
let boxActive = "full";         // "full" | "stuff"
let etatTri = { cle: null, direction: 1 };

// Filtre multi-élément/type, indépendant du tri, conservé séparément par vue
let filtreType = { characters: new Set(), weapons: new Set() };

// Données brutes du profil ouvert, conservées pour re-render sans refetch
let profilCourant = null;
let personnagesData = [];
let armesData = [];

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

async function chargerArmes() {
  const reponse = await fetch("../DB/weapons.json");
  if (!reponse.ok) {
    throw new Error("Impossible de charger les armes.");
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

function getLabelConstellation(valeur, vue) {
  if (valeur < 0) return "";
  return configCollections[vue].labels[valeur];
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

function getIconeItem(item, vue) {
  if (vue === "characters") {
    return iconesElements[item.element] || "";
  }
  return iconesTypesArmes[item.type] || "";
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

// ---- Construction de la liste affichée selon vue + box ----

function construireListeAffichee() {
  const config = configCollections[vueActive];
  const items = vueActive === "characters" ? personnagesData : armesData;
  const collectionProfil = profilCourant.data?.[vueActive] || { full: {}, selections: {} };
  const champType = vueActive === "characters" ? "element" : "type";
  const filtresActifs = filtreType[vueActive];

  return items
    .filter(item => {
      const valeur = collectionProfil.full?.[item.id] ?? -1;

      if (valeur < 0) {
        return false;
      }

      if (boxActive === "stuff" && !collectionProfil.selections?.stuff?.[item.id]) {
        return false;
      }

      if (filtresActifs.size > 0 && !filtresActifs.has(item[champType])) {
        return false;
      }

      return true;
    })
    .map(item => ({
      item,
      valeur: collectionProfil.full[item.id],
      config
    }));
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
      valA = Number(a.item[a.config.pointsField]?.[a.valeur] ?? 0);
      valB = Number(b.item[b.config.pointsField]?.[b.valeur] ?? 0);
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

function mettreAJourIconesFiltreType() {
  document.querySelectorAll(".type-sort-icone").forEach(btn => {
    const actif = filtreType[vueActive].has(btn.dataset.valeur);
    btn.classList.toggle("active", actif);
  });
}

function mettreAJourBoutonsVueEtBox() {
  document.querySelectorAll(".view-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.view === vueActive);
  });

  document.querySelectorAll(".box-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.box === boxActive);
  });
}

function creerCarteProfilPersonnage({ item, valeur, config }) {
  const card = document.createElement("div");
  card.className = "character-card";

  const fond = getFondRarete(item.rarete);
  const icone = getIconeItem(item, vueActive);

  card.innerHTML = `
    <div class="character-visuel" style="background-image: url('${fond}');">
      <img src="../DB/${item.image}" alt="${item.nom}">
      ${icone ? `<img class="character-icone-type" src="${icone}" alt="">` : ""}
      <div class="character-ppc-badge">${item[config.pointsField]?.[valeur] ?? ""}</div>
    </div>
    <div class="character-name">${item.nom}</div>
    <div class="character-level">${getLabelConstellation(valeur, vueActive)}</div>
  `;

  return card;
}

function rendreProfilBox() {
  const container = document.getElementById("profile-box");
  container.innerHTML = "";

  const liste = trierPersonnages(construireListeAffichee());

  liste.forEach(entree => {
    container.appendChild(creerCarteProfilPersonnage(entree));
  });
}

function genererBarreTypeSort() {
  const container = document.getElementById("type-sort-bar");
  container.innerHTML = "";

  const icones = vueActive === "characters" ? iconesElements : iconesTypesArmes;

  Object.entries(icones).forEach(([valeur, src]) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "type-sort-icone";
    btn.dataset.valeur = valeur;
    btn.innerHTML = `<img src="${src}" alt="${valeur}">`;

    btn.addEventListener("click", () => {
      const set = filtreType[vueActive];

      if (set.has(valeur)) {
        set.delete(valeur);
      } else {
        set.add(valeur);
      }

      mettreAJourIconesFiltreType();
      rendreProfilBox();
    });

    container.appendChild(btn);
  });

  mettreAJourIconesFiltreType();
}

function initialiserBarreTri() {
  document.querySelectorAll(".sort-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const cle = btn.dataset.sort;

      if (etatTri.cle === cle) {
        etatTri.direction *= -1;
      } else {
        etatTri.cle = cle;
        etatTri.direction = 1;
      }

      mettreAJourBoutonsTri();
      rendreProfilBox();
    });
  });
}

function initialiserSelecteursVueEtBox() {
  document.querySelectorAll(".view-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      vueActive = btn.dataset.view;

      mettreAJourBoutonsVueEtBox();
      genererBarreTypeSort();
      rendreProfilBox();
    });
  });

  document.querySelectorAll(".box-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      boxActive = btn.dataset.box;
      mettreAJourBoutonsVueEtBox();
      rendreProfilBox();
    });
  });
}

// ---- Ouverture / fermeture popup ----

async function ouvrirProfil(discordId, nom) {
  try {
    const [profil, personnages, armes] = await Promise.all([
      chargerProfil(discordId),
      chargerPersonnages(),
      chargerArmes()
    ]);

    profilCourant = profil;
    personnagesData = personnages;
    armesData = armes;

    vueActive = "characters";
    boxActive = "full";
    etatTri = { cle: null, direction: 1 };
    filtreType = { characters: new Set(), weapons: new Set() };

    mettreAJourBoutonsVueEtBox();
    genererBarreTypeSort();
    mettreAJourBoutonsTri();

    document.getElementById("modal-title").textContent = `Box de ${nom}`;
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
    initialiserSelecteursVueEtBox();
  } catch (error) {
    console.error(error);
    alert("Erreur lors du chargement des comptes.");
  }
}

demarrer();