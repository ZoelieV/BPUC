const {
  SESSION_TTL_SECONDS,
  parseCookies,
  setCookie,
  createSessionToken
} = require("../../_lib/session");
module.exports = async (req, res) => {
  try {
    const currentUrl = new URL(req.url, `https://${req.headers.host}`);
    const code = currentUrl.searchParams.get("code");
    const state = currentUrl.searchParams.get("state");

    const cookies = parseCookies(req);
    const savedState = cookies.discord_oauth_state;

    if (!code || !state || !savedState || state !== savedState) {
      return res.status(400).send("État OAuth invalide.");
    }

    const tokenResponse = await fetch("https://discord.com/api/oauth2/token", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded"      },
      body: new URLSearchParams({
        client_id: process.env.DISCORD_CLIENT_ID,
        client_secret: process.env.DISCORD_CLIENT_SECRET,
        grant_type: "authorization_code",
        code,
        redirect_uri: process.env.DISCORD_REDIRECT_URI      }).toString()
    });

    if (!tokenResponse.ok) {
      const text = await tokenResponse.text();
      console.error(text);
      return res.status(500).send("Échec échange token Discord.");
    }

    const tokenData = await tokenResponse.json();

    const userResponse = await fetch("https://discord.com/api/users/@me", {
      headers: {
        Authorization: `Bearer ${tokenData.access_token}`      }
    });

    if (!userResponse.ok) {
      const text = await userResponse.text();
      console.error(text);
      return res.status(500).send("Échec récupération profil Discord.");
    }

    const discordUser = await userResponse.json();

    const avatarUrl = discordUser.avatar      ? `https://cdn.discordapp.com/avatars/${discordUser.id}/${discordUser.avatar}.png?size=128`      : null;

    const user = {
      id: discordUser.id,
      username: discordUser.username,
      global_name: discordUser.global_name || null,
      avatar: avatarUrl
    };

    setCookie(res, "discord_oauth_state", "", {
      httpOnly: true,
      secure: true,
      sameSite: "Lax",
      path: "/",
      maxAge: 0    });

    setCookie(res, "session", createSessionToken(user), {
      httpOnly: true,
      secure: true,
      sameSite: "Lax",
      path: "/",
      maxAge: SESSION_TTL_SECONDS    });

    res.writeHead(302, {
      Location: process.env.AUTH_SUCCESS_REDIRECT || "/"    });
    res.end();
  } catch (error) {
    console.error(error);
    res.status(500).send("Erreur callback Discord.");
  }
};