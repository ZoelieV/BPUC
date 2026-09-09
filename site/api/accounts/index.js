const { createClient } = require("@supabase/supabase-js");
 
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);
 
module.exports = async (req, res) => {
  try {
    const { data, error } = await supabase
      .from("profiles")
      .select("discord_id, discord_username, discord_global_name, discord_avatar_url, updated_at")
      .order("updated_at", { ascending: false });
 
    if (error) {
      console.error(error);
      return res.status(500).json({ error: "Erreur chargement comptes" });
    }
 
    return res.status(200).json(data);
  } catch (error) {
    console.error(error);
    return res.status(500).json({ error: "Erreur serveur" });
  }
};