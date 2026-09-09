const { parseCookies, verifySessionToken } = require("../_lib/session");
module.exports = async (req, res) => {
  try {
    const cookies = parseCookies(req);
    const user = verifySessionToken(cookies.session);

    if (!user) {
      return res.status(401).json({
        authenticated: false      });
    }

    return res.status(200).json({
      authenticated: true,
      user
    });
  } catch (error) {
    console.error(error);
    res.status(500).json({ authenticated: false });
  }
};