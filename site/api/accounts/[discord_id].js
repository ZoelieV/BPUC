const { createClient } = require("@supabase/supabase-js");
 
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);
 
module.exports = async (req, res) => {
  try {
    const url = new URL(req.url, `https://${req.headers.host}`);
    const parts = url.pathname.split("/");
    const discordId = parts[parts.length - 1];
 
    const { data, error } = await supabase
      .from("profiles")
      .select("discord_id, discord_username, discord_global_name, discord_avatar_url, data")
      .eq("discord_id", discordId)
      .single();
 
    if (error) {
      console.error(error);
      return res.status(404).json({ error: "Profil introuvable" });
    }
 
    return res.status(200).json(data);
  } catch (error) {
    console.error(error);
    return res.status(500).json({ error: "Erreur serveur" });
  }
};