const { setCookie } = require("../_lib/session");
module.exports = async (req, res) => {
  try {
    setCookie(res, "session", "", {
      httpOnly: true,
      secure: true,
      sameSite: "Lax",
      path: "/",
      maxAge: 0    });

    res.writeHead(302, {
      Location: process.env.AUTH_LOGOUT_REDIRECT || "/"    });
    res.end();
  } catch (error) {
    console.error(error);
    res.status(500).send("Erreur déconnexion.");
  }
};