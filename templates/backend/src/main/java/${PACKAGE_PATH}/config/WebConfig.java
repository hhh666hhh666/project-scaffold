package ${PACKAGE}.config;

import ${PACKAGE}.security.JwtInterceptor;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.Arrays;

@Configuration
@RequiredArgsConstructor
public class WebConfig implements WebMvcConfigurer {

    private final JwtInterceptor jwtInterceptor;

    /**
     * 允许跨域的前端来源（逗号分隔）。默认空 = 不注册任何 CORS。
     *
     * 同源部署（前端与 /api 同域，由同一个反代暴露）压根不需要 CORS；
     * 只有本机换别的前端开发服务器、或将来前后端真的不同域时才设它。
     * 空值时刻意**不调用 registry.addMapping**，这样就不可能出现
     * 「allowedOriginPatterns("*") + allowCredentials(true)」那种在公网上等于门户大开的组合。
     */
    @Value("${CORS_ANNOTATION}")
    private String allowedOrigins;

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(jwtInterceptor)
                .addPathPatterns("/api/**")
                .excludePathPatterns(
                        "/api/auth/login",
                        "/api/auth/register",
                        // ⚠️ 脚手架的示例接口（首页靠它验证前后端连通）。接手后删掉这一行与示例模块。
                        "/api/example/hello",
                        "/swagger-ui/**",
                        "/swagger-ui.html",
                        "/v3/api-docs/**"
                );
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        String[] origins = allowedOrigins == null ? new String[0]
                : Arrays.stream(allowedOrigins.split(","))
                        .map(String::trim)
                        .filter(s -> !s.isEmpty())
                        .toArray(String[]::new);
        if (origins.length == 0) {
            return; // 同源部署：不注册 CORS
        }
        registry.addMapping("/**")
                .allowedOrigins(origins)
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                // JWT 走 Authorization 头、不用 cookie，所以不需要携带凭据；
                // 关掉它也让「来源被误写成通配」这件事不再有安全含义。
                .allowCredentials(false)
                .maxAge(3600);
    }
}
