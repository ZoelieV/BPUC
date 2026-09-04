const iconesElements = {
  pyro: "DB/images/others/pyro.webp",
  hydro: "DB/images/others/hydro.webp",
  anemo: "DB/images/others/anemo.webp",
  electro: "DB/images/others/electro.webp",
  cryo: "DB/images/others/cryo.webp",
  dendro: "DB/images/others/dendro.webp",
  geo: "DB/images/others/geo.webp"
};
 
const nomsBoxes = {
  full: "Full box",
  stuff: "Personnages stuff",
  opti1: "Box optimisée 1",
  opti2: "Box optimisée 2",
  opti3: "Box optimisée 3",
  opti4: "Box optimisée 4",
  opti5: "Box optimisée 5"
};
 
async function chargerPersonnages() {
  const reponse = await fetch("DB/characters.json");
  if (!reponse.ok) {
    throw new Error("Impossible de charger DB/characters.json");
  }
  return await reponse.json();
}
 
function creerProfilParDefaut() {
  return {
    uid: "",
    theatre: "",
    fullBox: {},
    selections: {
      stuff: {},
      opti1: {},
      opti2: {},
      opti3: {},
      opti4: {},
      opti5: {}
    }
  };
}
 
function chargerProfil() {
  const profilSauvegarde = localStorage.getItem("profil");
 
  if (!profilSauvegarde) {
    return creerProfilParDefaut();
  }
 
  const profil = JSON.parse(profilSauvegarde);
 
  if (!profil.fullBox) {
    profil.fullBox = profil.personnages || {};
  }
 
  if (!profil.selections) {
    profil.selections = {
      stuff: {},
      opti1: {},
      opti2: {},
      opti3: {},
      opti4: {},
      opti5: {}
    };
  }
 
  delete profil.personnages;
  return profil;
}
 
function sauvegarderProfil(profil) {
  localStorage.setItem("profil", JSON.stringify(profil));
}
 
function getBoxActive() {
  return document.querySelector(".box-btn.active")?.dataset.box || "full";
}
 
function setBoxActive(box) {
  document.querySelectorAll(".box-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.box === box);
  });
}
 
function getFondRarete(rarete) {
  const valeur = String(rarete);
 
  if (valeur === "5") {
    return "DB/images/others/bg_5_star.webp";
  }
 
  if (valeur === "3") {
    return "DB/images/others/bg_3_star.webp";
  }
 
  return "DB/images/others/bg_4_star.webp";
}
 
function getPPC(personnage, constellation) {
  if (constellation < 0) {
    return "";
  }
 
  return personnage.PPC?.[constellation] ?? "";
}
 
function creerBadgePPC(valeur) {
  const badge = document.createElement("div");
  badge.className = "ppc-badge";
  badge.textContent = valeur;
  return badge;
}
 
function creerCartePersonnage(personnage, constellation = -1, boxActive = "full", selectionne = false) {
  const conteneur = document.createElement("div");
  conteneur.className = "carte-personnage";
 
  const fond = getFondRarete(personnage.rarete);
  const imageElement = iconesElements[personnage.element] || "";
  const affichageConstellation = constellation < 0 ? "-" : `C${constellation}`;
 
  const opacite = boxActive === "full"
    ? (constellation < 0 ? "0.4" : "1")
    : (selectionne ? "1" : "0.45");
 
  const zoneAction = boxActive === "full"
    ? `
<div class="controle-constellation">
<button type="button" class="constellation-btn moins-btn" data-id="${personnage.id}">-</button>
<span>${affichageConstellation}</span>
<button type="button" class="constellation-btn plus-btn" data-id="${personnage.id}">+</button>
</div>
    `
    : `
<label class="toggle-box-label">
<input type="checkbox" class="switch-box" data-id="${personnage.id}" ${selectionne ? "checked" : ""}>
        Dans la box
</label>
    `;
 
  conteneur.innerHTML = `
<div class="visuel-personnage" style="background-image: url('${fond}'); opacity: ${opacite};">
<img class="image-personnage" src="DB/${personnage.image}" alt="${personnage.nom}">
      ${imageElement ? `<img class="icone-element" src="${imageElement}" alt="${personnage.element}">` : ""}
</div>
 
    <div class="nom-personnage">${personnage.nom}</div>
<div class="info-constellation">${affichageConstellation}</div>
    ${zoneAction}
  `;
 
  if (constellation >= 0) {
    conteneur.querySelector(".visuel-personnage").appendChild(
      creerBadgePPC(getPPC(personnage, constellation))
    );
  }
 
  return conteneur;
}
 
function afficherPersonnages(personnages, profil) {
  const liste = document.getElementById("liste-personnages");
  liste.innerHTML = "";
 
  const boxActive = getBoxActive();
 
  const elementsSelectionnes = Array.from(document.querySelectorAll(".filtre-element:checked"))
    .map(input => input.value);
 
  const armesSelectionnees = Array.from(document.querySelectorAll(".filtre-arme:checked"))
    .map(input => input.value);
 
  const rareteSelectionnees = Array.from(document.querySelectorAll(".filtre-rarete:checked"))
    .map(input => input.value);
 
  const personnagesFiltres = personnages.filter(personnage => {
    const filtreElementOK =
      elementsSelectionnes.length === 0 || elementsSelectionnes.includes(personnage.element);
 
    const filtreArmeOK =
      armesSelectionnees.length === 0 || armesSelectionnees.includes(personnage.arme);
 
    const filtreRareteOK =
      rareteSelectionnees.length === 0 || rareteSelectionnees.includes(String(personnage.rarete));
 
    if (boxActive !== "full" && (profil.fullBox[personnage.id] ?? -1) < 0) {
      return false;
    }
 
    return filtreElementOK && filtreArmeOK && filtreRareteOK;
  });
 
  personnagesFiltres.forEach(personnage => {
    const constellation = profil.fullBox[personnage.id] ?? -1;
    const selectionne = boxActive === "full"
      ? constellation >= 0
      : !!profil.selections[boxActive][personnage.id];
 
    const carte = creerCartePersonnage(personnage, constellation, boxActive, selectionne);
    liste.appendChild(carte);
  });
}
 
function mettreAJourTotalBox(personnages, profil) {
  const boxActive = getBoxActive();
  let total = 0;
 
  personnages.forEach(personnage => {
    const constellation = profil.fullBox[personnage.id] ?? -1;
 
    if (constellation < 0) {
      return;
    }
 
    const inclus = boxActive === "full"
      ? true
      : !!profil.selections[boxActive][personnage.id];
 
    if (inclus) {
      total += Number(personnage.PPC?.[constellation] ?? 0);
    }
  });
 
  document.getElementById("box-total-label").textContent = nomsBoxes[boxActive];
  document.getElementById("total-ppc").textContent = total;
}
 
async function initialiserPage() {
  try {
    const personnages = await chargerPersonnages();
    const profil = chargerProfil();
 
    document.getElementById("uid").value = profil.uid || "";
    document.getElementById("theatre").value = profil.theatre || "";
 
    setBoxActive("full");
    afficherPersonnages(personnages, profil);
    mettreAJourTotalBox(personnages, profil);
 
    document.querySelectorAll(".filtre-element, .filtre-arme, .filtre-rarete").forEach(input => {
      input.addEventListener("change", () => {
        afficherPersonnages(personnages, profil);
        mettreAJourTotalBox(personnages, profil);
      });
    });
 
    document.querySelectorAll(".box-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        setBoxActive(btn.dataset.box);
        afficherPersonnages(personnages, profil);
        mettreAJourTotalBox(personnages, profil);
      });
    });
 
    const liste = document.getElementById("liste-personnages");
 
    liste.addEventListener("click", event => {
      if (getBoxActive() !== "full") {
        return;
      }
 
      const boutonMoins = event.target.closest(".moins-btn");
      const boutonPlus = event.target.closest(".plus-btn");
 
      if (!boutonMoins && !boutonPlus) {
        return;
      }
 
      const id = (boutonMoins || boutonPlus).dataset.id;
      let valeur = profil.fullBox[id] ?? -1;
 
      if (boutonPlus) {
        valeur = valeur === 6 ? -1 : valeur + 1;
      }
 
      if (boutonMoins) {
        valeur = valeur === -1 ? 6 : valeur - 1;
      }
 
      profil.fullBox[id] = valeur;
 
      if (valeur < 0) {
        Object.keys(profil.selections).forEach(box => {
          delete profil.selections[box][id];
        });
      }
 
      afficherPersonnages(personnages, profil);
      mettreAJourTotalBox(personnages, profil);
    });
 
    liste.addEventListener("change", event => {
      const switchBox = event.target.closest(".switch-box");
 
      if (!switchBox) {
        return;
      }
 
      const boxActive = getBoxActive();
 
      if (boxActive === "full") {
        return;
      }
 
      if (switchBox.checked) {
        profil.selections[boxActive][switchBox.dataset.id] = true;
      } else {
        delete profil.selections[boxActive][switchBox.dataset.id];
      }
 
      afficherPersonnages(personnages, profil);
      mettreAJourTotalBox(personnages, profil);
    });
 
    document.getElementById("profil-form").addEventListener("submit", event => {
      event.preventDefault();
 
      profil.uid = document.getElementById("uid").value;
      profil.theatre = document.getElementById("theatre").value;
 
      sauvegarderProfil(profil);
      alert("Profil enregistré");
    });
  } catch (erreur) {
    console.error(erreur);
    alert("Erreur lors du chargement de la page.");
  }
}
 
initialiserPage();