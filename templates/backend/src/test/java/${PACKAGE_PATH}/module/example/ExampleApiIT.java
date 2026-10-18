package ${PACKAGE}.module.example;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 集成测试样例：**一个类同时证明四件事**——
 *
 * <ol>
 *   <li>Spring 上下文能在真 MySQL 上启动；</li>
 *   <li>Flyway 的 V1 迁移真的执行了（迁移是 MySQL 方言，H2 验不了）；</li>
 *   <li>JWT 拦截器把白名单接口放行，接口能返回 200；</li>
 *   <li>统一响应信封 Result 的序列化形状没坏。</li>
 * </ol>
 *
 * <p>它归 failsafe（文件名以 {@code IT} 结尾），所以 {@code mvn test} 不会跑它、
 * 也不需要 Docker；{@code mvn verify} 才会起容器。
 *
 * <p>写新的集成测试照这个形状：{@code @SpringBootTest(RANDOM_PORT)} +
 * {@code @Testcontainers} + {@code @ServiceConnection}。不要用 H2 替代 MySQL，
 * 也不要把需要落库的逻辑塞回 {@code *Test}。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
class ExampleApiIT {

    /**
     * 镜像版本与版本表、两份 compose 保持一致；由一致性检查盯着。
     * {@code @ServiceConnection} 会把连接信息自动交给数据源，不需要手写 DynamicPropertySource。
     */
    @Container
    @ServiceConnection
    static MySQLContainer<?> mysql = new MySQLContainer<>("mysql:8");

    @Autowired
    TestRestTemplate restTemplate;

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
}
