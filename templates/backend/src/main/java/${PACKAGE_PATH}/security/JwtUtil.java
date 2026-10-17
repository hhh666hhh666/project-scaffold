package ${PACKAGE}.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.UUID;

@Slf4j
@Component
public class JwtUtil {

    /**
     * 配置文件里的兜底默认值。它随仓库一起被看见，等于一把公开的钥匙，
     * 谁都能拿它签发任意 userId 的 token，绝不能真正用于签名。
     */
    private static final String INSECURE_DEFAULT_SECRET = "${JWT_DEFAULT_SECRET}";

    private final SecretKey key;
    private final long expireMillis;

    // 读 application.yml 的配置键，别直接读环境变量：兜底默认值只在 yml 里，
    // 直接读环境变量会让「没设密钥」变成启动失败，下面的随机密钥兜底也就永远走不到。
    public JwtUtil(@Value("${JWT_SECRET_ANNOTATION}") String secret,
                   @Value("${JWT_EXPIRE_ANNOTATION}") long expireDays) {
        this.key = Keys.hmacShaKeyFor(resolveSecret(secret).getBytes(StandardCharsets.UTF_8));
        this.expireMillis = expireDays * 24 * 60 * 60 * 1000L;
    }

    /**
     * 没配 JWT 密钥时不能直接用那个公开的默认值签名，改为每次启动随机生成一把：
     * 安全性兜住了，代价只是重启后需要重新登录。（仅影响本机开发；容器里由 .env 注入真实密钥。）
     */
    private String resolveSecret(String secret) {
        if (!INSECURE_DEFAULT_SECRET.equals(secret)) {
            return secret;
        }
        String random = UUID.randomUUID().toString().replace("-", "") + UUID.randomUUID();
        log.warn("\n" +
                "****************************************************************************\n" +
                "* 正在使用 JWT 默认密钥，该值已随仓库公开，任何人都能伪造 token。\n" +
                "* 本次启动已改用随机密钥代替（重启后已登录用户需重新登录）。\n" +
                "* 正式环境请在 .env 里设置 ${APP_ENV_PREFIX}_JWT_SECRET：\n" +
                "*   python -c \"import secrets;print(secrets.token_hex(32))\"\n" +
                "****************************************************************************");
        return random;
    }

    public String generateToken(Long userId) {
        Date now = new Date();
        return Jwts.builder()
                .subject(String.valueOf(userId))
                .issuedAt(now)
                .expiration(new Date(now.getTime() + expireMillis))
                .signWith(key)
                .compact();
    }

    public long getExpireMillis() {
        return expireMillis;
    }

    /**
     * 解析 token，失败返回 null。
     */
    public Long parseToken(String token) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(key)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
            return Long.valueOf(claims.getSubject());
        } catch (JwtException | IllegalArgumentException e) {
            log.debug("invalid jwt token: {}", e.getMessage());
            return null;
        }
    }
}
