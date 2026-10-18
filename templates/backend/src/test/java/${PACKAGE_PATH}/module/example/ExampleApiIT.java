package ${PACKAGE}.module.example;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

import ${PACKAGE}.security.JwtUtil;
import ${PACKAGE}.support.IntegrationTestBase;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 集成测试样例：**一个类同时证明五件事**——
 *
 * <ol>
 *   <li>Spring 上下文能在真 MySQL 上启动；</li>
 *   <li>Flyway 的 V1 迁移真的执行了（迁移是 MySQL 方言，H2 验不了）；</li>
 *   <li>JWT 拦截器把白名单接口放行，接口能返回 200；</li>
 *   <li>统一响应信封 Result 的序列化形状没坏；</li>
 *   <li><b>鉴权契约</b>：受保护接口缺 token 时返回 HTTP 200 + 信封 code 401，
 *       带合法 token 时放行——前端的「未登录跳转」依赖的正是这条。</li>
 * </ol>
 *
 * <p>它归 failsafe（文件名以 {@code IT} 结尾），所以 {@code mvn test} 不会跑它、
 * 也不需要 Docker；{@code mvn verify} 才会起容器。
 *
 * <p>写新的集成测试照这个形状：{@code extends IntegrationTestBase} +
 * {@code @SpringBootTest(RANDOM_PORT)}。**不要在子类里再声明容器**——
 * 基类已经共享了一个，重复声明会按类再起一个。错误响应的形状另见
 * {@code ExampleErrorContractIT}。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ExampleApiIT extends IntegrationTestBase {

    @Autowired
    TestRestTemplate restTemplate;

    @Autowired
    JwtUtil jwtUtil;

    @Test
    void helloEndpointWorksThroughRealSpringContextAndDatabase() {
        ResponseEntity<Map<String, Object>> response = restTemplate.exchange(
                "/api/example/hello?name=IT",
                HttpMethod.GET,
                null,
                new ParameterizedTypeReference<>() {
                });

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        Map<String, Object> body = response.getBody();
        assertThat(body).isNotNull();
        assertThat(body.get("code")).isEqualTo(0);

        Object data = body.get("data");
        assertThat(data).isInstanceOf(Map.class);
        Map<?, ?> payload = (Map<?, ?>) data;
        assertThat(payload.get("message")).isEqualTo("hello, IT");
        assertThat(payload.get("fromBackend")).isEqualTo(true);
    }

    @Test
    void healthEndpointReportsUpWithDatabase() {
        ResponseEntity<Map<String, Object>> response = restTemplate.exchange(
                "/actuator/health",
                HttpMethod.GET,
                null,
                new ParameterizedTypeReference<>() {
                });

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).containsEntry("status", "UP");
    }

    /**
     * 前端「未登录就跳登录页」依赖这里：**HTTP 状态码是 200，成败在信封的 code 里**。
     * 哪天有人把拦截器改成返回真正的 HTTP 401，这条会先红，而不是等前端静默失效。
     */
    @Test
    void protectedEndpointRejectsMissingTokenWithEnvelope401() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        ResponseEntity<Map<String, Object>> response = restTemplate.exchange(
                "/api/example/echo",
                HttpMethod.POST,
                new HttpEntity<>(Map.of("name", "IT"), headers),
                new ParameterizedTypeReference<>() {
                });

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).containsEntry("code", 401);
    }

    @Test
    void protectedEndpointAcceptsValidToken() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(jwtUtil.generateToken(1L));

        ResponseEntity<Map<String, Object>> response = restTemplate.exchange(
                "/api/example/echo",
                HttpMethod.POST,
                new HttpEntity<>(Map.of("name", "IT"), headers),
                new ParameterizedTypeReference<>() {
                });

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).containsEntry("code", 0);
    }
}
