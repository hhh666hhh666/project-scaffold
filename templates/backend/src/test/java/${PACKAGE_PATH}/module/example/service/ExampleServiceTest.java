package ${PACKAGE}.module.example.service;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * 单元层样例：**纯 JUnit 5**，不拉 Spring 上下文、不触发迁移脚本、**不需要数据库**。
 *
 * <p>这条约束是有意为之——它让 `mvn test` 在任何机器上都能跑、不需要起任何服务。
 * 加测试时**别破坏它**：确实需要库的逻辑放进 `*IT`（归 failsafe，另跑）。
 *
 * <p>单元层的选题判据：**只测静默错误**——错了不报错、只会一直错下去的那种逻辑。
 */
class ExampleServiceTest {

    private final ExampleService service = new ExampleService();

    @Test
    void greeting_usesGivenName() {
        assertEquals("hello, world", service.greeting("world"));
    }

    @Test
    void greeting_trimsSurroundingSpaces() {
        assertEquals("hello, world", service.greeting("  world  "));
    }

    @Test
    void greeting_fallsBackWhenBlank() {
        assertEquals("hello, world", service.greeting("   "));
        assertEquals("hello, world", service.greeting(null));
    }
}
