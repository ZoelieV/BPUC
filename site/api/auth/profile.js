const { parseCookies, verifySessionToken } = require("../_lib/session");

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

function getUser(req) {
  const cookies = parseCookies(req);
  const token = cookies["session"];
  return verifySessionToken(token);
}

module.exports = async (req, res) => {
  try {
    if (!SUPABASE_URL || !SUPABASE_KEY) {
      return res.status(500).json({ error: "Variables Supabase manquantes." });
    }

    const user = getUser(req);
    if (!user) {
      return res.status(401).json({ error: "Non connecté" });
    }

    const discordId = user.id;

    // ---- LECTURE DU PROFIL ----
    if (req.method === "GET") {
      const r = await fetch(
        `${SUPABASE_URL}/rest/v1/profiles?discord_id=eq.${discordId}&select=data`,
        {
          headers: {
            apikey: SUPABASE_KEY,
            Authorization: `Bearer ${SUPABASE_KEY}`
          }
        }
      );

      if (!r.ok) {
        const text = await r.text();
        console.error(text);
        return res.status(500).json({ error: "Erreur lecture profil." });
      }

      const rows = await r.json();
      return res.status(200).json({ profil: rows[0]?.data || null });
    }

    // ---- SAUVEGARDE DU PROFIL ----
    if (req.method === "POST") {
      let body = "";
      for await (const chunk of req) {
        body += chunk;
      }

      let profil;
      try {
        profil = JSON.parse(body);
      } catch {
        return res.status(400).json({ error: "JSON invalide." });
      }

      const r = await fetch(`${SUPABASE_URL}/rest/v1/profiles`, {
        method: "POST",
        headers: {
          apikey: SUPABASE_KEY,
          Authorization: `Bearer ${SUPABASE_KEY}`,
          "Content-Type": "application/json",
          Prefer: "resolution=merge-duplicates"
        },
        body: JSON.stringify({
          discord_id: discordId,
          data: profil,
          updated_at: new Date().toISOString()
        })
      });

      if (!r.ok) {
        const text = await r.text();
        console.error(text);
        return res.status(500).json({ error: "Erreur sauvegarde profil." });
      }

      return res.status(200).json({ ok: true });
    }

    res.setHeader("Allow", "GET, POST");
    return res.status(405).end();
  } catch (error) {
    console.error(error);
    return res.status(500).json({ error: "Erreur serveur." });
  }
};