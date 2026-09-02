const iconesElements = {
  Pyro: "images/elements/pyro.png",
  Hydro: "images/elements/hydro.png",
  Anemo: "images/elements/anemo.png",
  Electro: "images/elements/electro.png",
  Cryo: "images/elements/cryo.png",
  Dendro: "images/elements/dendro.png",
  Geo: "images/elements/geo.png"
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
 
function creerCartePersonnage(personnage, valeurEnregistree = -1) {
  const conteneur = document.createElement("div");
 
  let fond = "";
  if (personnage.rarete === "5") {
    fond = "images/backgrounds/bg_5star.png";
  } else {
    fond = "images/backgrounds/bg_4star.png";
  }
 
  const imageElement = iconesElements[personnage.element] || "";
 
  conteneur.innerHTML = `
<div style="display: inline-block; margin: 6px; text-align: center;">
<div style="position: relative; display: inline-block; background-image: url('${fond}'); background-size: cover; background-position: center; padding: 6px;">
<img src="DB/${personnage.image}" alt="${personnage.nom}" width="80">
        ${
          imageElement
            ? `<img src="${imageElement}" alt="${personnage.element}" width="20" style="position: absolute; top: 0; left: 0;">`
            : ""
        }
</div>
<div>${personnage.nom}</div>
<label>
<select data-id="${personnage.id}">
<option value="-1" ${valeurEnregistree === -1 ? "selected" : ""}>Non possédé</option>
<option value="0" ${valeurEnregistree === 0 ? "selected" : ""}>C0</option>
<option value="1" ${valeurEnregistree === 1 ? "selected" : ""}>C1</option>
<option value="2" ${valeurEnregistree === 2 ? "selected" : ""}>C2</option>
<option value="3" ${valeurEnregistree === 3 ? "selected" : ""}>C3</option>
<option value="4" ${valeurEnregistree === 4 ? "selected" : ""}>C4</option>
<option value="5" ${valeurEnregistree === 5 ? "selected" : ""}>C5</option>
<option value="6" ${valeurEnregistree === 6 ? "selected" : ""}>C6</option>
</select>
</label>
</div>
  `;
 
  return conteneur;
}
 
async function initialiserPage() {
  const personnages = await chargerPersonnages();
  const profil = chargerProfil();
 
  document.getElementById("uid").value = profil.uid || "";
  document.getElementById("theatre").value = profil.theatre || "";
 
  const liste = document.getElementById("liste-personnages");
  liste.innerHTML = "";
 
  personnages.forEach(personnage => {
    const valeur = profil.personnages[personnage.id] ?? -1;
    const carte = creerCartePersonnage(personnage, valeur);
    liste.appendChild(carte);
  });
 
  document.getElementById("profil-form").addEventListener("submit", function(event) {
    event.preventDefault();
 
    const nouveauProfil = {
      uid: document.getElementById("uid").value,
      theatre: document.getElementById("theatre").value,
      personnages: {}
    };
 
    const selects = document.querySelectorAll("#liste-personnages select");
 
    selects.forEach(select => {
      nouveauProfil.personnages[select.dataset.id] = Number(select.value);
    });
 
    sauvegarderProfil(nouveauProfil);
    alert("Profil enregistré");
  });
}
 
initialiserPage();
