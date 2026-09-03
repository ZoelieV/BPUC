const iconesElements = {
  pyro: "DB/images/others/pyro.png",
  hydro: "DB/images/others/hydro.png",
  anemo: "DB/images/others/anemo.png",
  electro: "DB/images/others/electro.png",
  cryo: "DB/images/others/cryo.png",
  dendro: "DB/images/others/dendro.png",
  geo: "DB/images/others/geo.png"
};
 
async function chargerPersonnages() {
  const reponse = await fetch("DB/characters.json")
  return await reponse.json();
}
 
function chargerProfil() {
  const profilSauvegarde = localStorage.getItem("profil");
  if (profilSauvegarde) {
    return JSON.parse(profilSauvegarde);
  }
 
  return {
    uid: "",
    theatre: "",
    personnages: {}
  };
}
 
function sauvegarderProfil(profil) {
  localStorage.setItem("profil", JSON.stringify(profil));
}

function afficherPersonnages(personnages, profil) {
  const liste = document.getElementById("liste-personnages");
  liste.innerHTML = "";
 
  const elementsSelectionnes = Array.from(document.querySelectorAll(".filtre-element:checked"))
    .map(input => input.value);
 
  const armesSelectionnees = Array.from(document.querySelectorAll(".filtre-arme:checked"))
    .map(input => input.value);
 
  const personnagesFiltres = personnages.filter(personnage => {
    const filtreElementOK =
      elementsSelectionnes.length === 0 || elementsSelectionnes.includes(personnage.element);
 
    const filtreArmeOK =
      armesSelectionnees.length === 0 || armesSelectionnees.includes(personnage.arme);
 
    return filtreElementOK && filtreArmeOK;
  });
 
  personnagesFiltres.forEach(personnage => {
    const valeur = profil.personnages[personnage.id] ?? -1;
    const carte = creerCartePersonnage(personnage, valeur);
    liste.appendChild(carte);
  });
}
 
function creerCartePersonnage(personnage, valeurEnregistree = -1) {
  const conteneur = document.createElement("div");
 
  let fond = "";
  if (personnage.rarete === "5") {
    fond = "DB/images/others/bg_5_star.png";
  } else if (personnage.rarete === "3") {
    fond = "DB/images/others/bg_3_star.png";
  } else {
    fond = "DB/images/others/bg_4_star.png";
  }
 
  const imageElement = iconesElements[personnage.element] || "";
  const affichageConstellation = valeurEnregistree < 0 ? "-" : "C" + valeurEnregistree;
  const opacite = valeurEnregistree < 0 ? "0.4" : "1";
 
  conteneur.innerHTML = `
<div style="width: 120px; text-align: center;">
<div class="visuel-personnage" style="position: relative; display: inline-block; background-image: url('${fond}'); background-size: cover; background-position: center; padding: 6px; opacity: ${opacite};">
<img src="DB/${personnage.image}" alt="${personnage.nom}" width="80" style="border-radius: 8px;">
        ${
          imageElement
            ? `<img src="${imageElement}" alt="${personnage.element}" width="20" style="position: absolute; top: 2px; left: 2px;">`
            : ""
        }
</div>
 
      <div>${personnage.nom}</div>
 
      <div>
<button type="button" class="moins-btn" data-id="${personnage.id}" style="width: 28px; height: 28px; font-size: 18px; font-weight: bold; border-radius: 6px;">-</button>
<span class="constellation-valeur" data-id="${personnage.id}">${affichageConstellation}</span>
<button type="button" class="plus-btn" data-id="${personnage.id}" style="width: 28px; height: 28px; font-size: 18px; font-weight: bold; border-radius: 6px;">+</button>
</div>
 
      <input type="hidden" class="constellation-input" data-id="${personnage.id}" value="${valeurEnregistree}">
</div>
  `;
 
  return conteneur;
}
 
async function initialiserPage() {
  const personnages = await chargerPersonnages();
  const profil = chargerProfil();
 
  document.getElementById("uid").value = profil.uid || "";
  document.getElementById("theatre").value = profil.theatre || "";
 
  afficherPersonnages(personnages, profil);
  
  document.querySelectorAll(".filtre-element, .filtre-arme").forEach(input => {
    input.addEventListener("change", () => {
      afficherPersonnages(personnages, profil);
    });
  });
  
  const liste = document.getElementById("liste-personnages");

  liste.addEventListener("click", function(event) {
    const boutonMoins = event.target.closest(".moins-btn");
    const boutonPlus = event.target.closest(".plus-btn");
 
    if (!boutonMoins && !boutonPlus) {
      return;
    }
 
    const id = (boutonMoins || boutonPlus).dataset.id;
    const input = document.querySelector(`.constellation-input[data-id="${id}"]`);
    const affichage = document.querySelector(`.constellation-valeur[data-id="${id}"]`);
    const visuel = input.parentElement.querySelector(".visuel-personnage");
 
    let valeur = Number(input.value);
 
    if (boutonPlus) {
      if (valeur === 6) {
        valeur = -1;
      } else {
        valeur++;
      }
    }
    
    if (boutonMoins) {
      if (valeur === -1) {
        valeur = 6;
      } else {
        valeur--;
      }
    }
 
    input.value = valeur;
    affichage.textContent = valeur < 0 ? "-" : "C" + valeur;
    visuel.style.opacity = valeur < 0 ? "0.4" : "1";
  });
 
  document.getElementById("profil-form").addEventListener("submit", function(event) {
    event.preventDefault();
  
    const nouveauProfil = {
      uid: document.getElementById("uid").value,
      theatre: document.getElementById("theatre").value,
      personnages: {}
    };
  
    const inputs = document.querySelectorAll(".constellation-input");
  
    inputs.forEach(input => {
      nouveauProfil.personnages[input.dataset.id] = Number(input.value);
    });
  
    sauvegarderProfil(nouveauProfil);
    alert("Profil enregistré");
  });
}
 
initialiserPage();
