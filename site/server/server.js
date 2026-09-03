const express = require("express");
const fs = require("fs");
const path = require("path");
 
const app = express();
const PORT = 3000;
 
const siteDir = path.join(__dirname, "..");
const fichierBoxes = path.join(siteDir, "..", "DB", "local_boxes.json");
const fichierRooms = path.join(siteDir, "DB", "rooms.json");
 
app.use(express.json());
app.use(express.static(siteDir));
 
app.get("/", (req, res) => {
  res.sendFile(path.join(siteDir, "base.html"));
});
 
app.get("/api/boxes/:boxId", (req, res) => {
  const boxId = req.params.boxId;
 
  let data = {};
  if (fs.existsSync(fichierBoxes)) {
    data = JSON.parse(fs.readFileSync(fichierBoxes, "utf8"));
  }
 
  res.json(data[boxId] || null);
});

app.post("/api/boxes/:boxId", (req, res) => {
  const boxId = req.params.boxId;
  const contenu = req.body;
 
  let data = {};
  if (fs.existsSync(fichierBoxes)) {
    data = JSON.parse(fs.readFileSync(fichierBoxes, "utf8"));
  }
 
  data[boxId] = contenu;
 
  fs.writeFileSync(fichierBoxes, JSON.stringify(data, null, 2), "utf8");
 
  res.json({ ok: true });
});
function lireRooms() {
  if (!fs.existsSync(fichierRooms)) {
    fs.writeFileSync(fichierRooms, "{}", "utf8");
  }
 
  return JSON.parse(fs.readFileSync(fichierRooms, "utf8"));
}
 
function ecrireRooms(data) {
  fs.writeFileSync(fichierRooms, JSON.stringify(data, null, 2), "utf8");
}
 
function genererRoomId() {
  return Math.random().toString(36).substring(2, 8);
}
 
app.post("/api/rooms", (req, res) => {
  const rooms = lireRooms();
 
  let roomId = genererRoomId();
  while (rooms[roomId]) {
    roomId = genererRoomId();
  }
 
  rooms[roomId] = {
    players: ["j1"]
  };
 
  ecrireRooms(rooms);
 
  res.json({ ok: true, roomId });
});
 
app.get("/api/rooms/:roomId/join", (req, res) => {
  const roomId = req.params.roomId;
  const rooms = lireRooms();
 
  if (!rooms[roomId]) {
    res.json({ ok: false, error: "Room introuvable" });
    return;
  }
 
  const joueurs = rooms[roomId].players;
 
  if (joueurs.includes("j2")) {
    res.json({ ok: false, error: "Room pleine" });
    return;
  }
 
  if (!joueurs.includes("j2")) {
    joueurs.push("j2");
    ecrireRooms(rooms);
  }
 
  res.json({ ok: true, player: "j2" });
});
 
app.listen(PORT, "0.0.0.0", () => {
  console.log(`Serveur lancé sur http://localhost:${PORT}`);
});
 